"""Handler tests with an in-memory fake for DynamoDB (no AWS needed)."""
import json
from contextlib import contextmanager

from handlers import report_handler, scan_handler, stats_handler

MOCKUP = (
    "Hi! Your resume was selected for a Remote Data Entry Associate role at Amazon ($42/hr). "
    "Interviews are conducted on Telegram - add @amzn_hr_team. Once hired, purchase your home-office kit ($450) "
    "through our approved vendor and you'll be reimbursed with your first check. "
    "Please respond within 2 hours to keep your spot."
)


class FakeTable:
    def __init__(self, key):
        self.key, self.items = key, {}

    def get_item(self, Key):
        item = self.items.get(Key[self.key])
        return {"Item": dict(item)} if item else {}

    def put_item(self, Item):
        self.items[Item[self.key]] = dict(Item)

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues, ReturnValues):
        item = self.items.setdefault(Key[self.key], {self.key: Key[self.key]})
        item["reportCount"] = item.get("reportCount", 0) + 1
        item["contactType"] = ExpressionAttributeValues[":t"]
        return {"Attributes": dict(item)}

    def query(self, IndexName, KeyConditionExpression, **_):
        day = KeyConditionExpression._values[1]
        return {"Items": [i for i in self.items.values() if i.get("day") == day]}


@contextmanager
def fake_aws():
    tables = {
        "SCANS_TABLE": FakeTable("scanId"),
        "REPORTS_TABLE": FakeTable("contactHash"),
        "DOMAIN_CACHE_TABLE": FakeTable("domain"),
    }
    saved = {}
    for mod in (scan_handler, report_handler, stats_handler):
        saved[mod] = mod.table
        mod.table = tables.__getitem__
    saved_rdap = scan_handler.rdap_created_date
    scan_handler.rdap_created_date = lambda d, timeout: "2026-10-25"
    try:
        yield tables
    finally:
        for mod, fn in saved.items():
            mod.table = fn
        scan_handler.rdap_created_date = saved_rdap


def post(body, claims=None):
    event = {"body": json.dumps(body)}
    if claims:
        event["requestContext"] = {"authorizer": {"jwt": {"claims": claims}}}
    return event


def body_of(resp):
    return json.loads(resp["body"])


def test_scan_mockup_message():
    with fake_aws() as t:
        resp = scan_handler.handler(post({"message": MOCKUP, "senderEmail": "careers.amazon.hr@gmail.com",
                                          "link": "https://amazon-remote-jobs.net/start"}), None)
        out = body_of(resp)
        assert resp["statusCode"] == 200
        assert out["label"] == "LIKELY_SCAM" and out["score"] == 100
        assert "NEW_DOMAIN" in {f["id"] for f in out["flags"]}
        saved = t["SCANS_TABLE"].items[out["scanId"]]
        assert "message" not in saved and MOCKUP not in json.dumps(saved)
        assert t["DOMAIN_CACHE_TABLE"].items["amazon-remote-jobs.net"]["createdDate"] == "2026-10-25"


def test_scan_validation():
    with fake_aws():
        assert scan_handler.handler(post({"message": "too short"}), None)["statusCode"] == 400
        assert scan_handler.handler(post({"message": "x" * 5001}), None)["statusCode"] == 400
        assert scan_handler.handler(post({"message": MOCKUP, "senderEmail": "not-an-email"}), None)["statusCode"] == 400
        assert scan_handler.handler(post({"message": MOCKUP, "link": "javascript:alert(1)"}), None)["statusCode"] == 400
        assert scan_handler.handler({"body": "{not json"}, None)["statusCode"] == 400


def test_report_needs_login():
    with fake_aws():
        resp = report_handler.handler(post({"contactType": "EMAIL", "contact": "a@gmail.com"}), None)
        assert resp["statusCode"] == 401


def test_report_then_scan_shows_community_flag():
    with fake_aws() as t:
        report = {"contactType": "EMAIL", "contact": "Careers.Amazon.HR@gmail.com", "platform": "EMAIL", "claimedCompany": "Amazon"}
        r1 = report_handler.handler(post(report, {"sub": "user-1"}), None)
        r2 = report_handler.handler(post(report, {"sub": "user-2"}), None)
        assert body_of(r1)["reportCount"] == 1 and body_of(r2)["reportCount"] == 2
        stored = json.dumps(list(t["REPORTS_TABLE"].items.values()))
        assert "careers.amazon.hr" not in stored.lower()

        out = body_of(scan_handler.handler(post({"message": "Hello, are you open to a remote job offer?",
                                                 "senderEmail": "careers.amazon.hr@gmail.com"}), None))
        assert out["communityReports"] == 2
        assert "COMMUNITY_REPORTED" in {f["id"] for f in out["flags"]}


def test_report_validation():
    with fake_aws():
        claims = {"sub": "u"}
        assert report_handler.handler(post({"contactType": "FAX", "contact": "x"}, claims), None)["statusCode"] == 400
        assert report_handler.handler(post({"contactType": "EMAIL", "contact": "nope"}, claims), None)["statusCode"] == 400
        assert report_handler.handler(post({"contactType": "PHONE", "contact": "12"}, claims), None)["statusCode"] == 400


def test_stats_counts_flag_types():
    with fake_aws():
        for _ in range(3):
            scan_handler.handler(post({"message": MOCKUP, "senderEmail": "careers.amazon.hr@gmail.com"}), None)
        resp = stats_handler.handler({"queryStringParameters": {"range": "week"}}, None)
        out = body_of(resp)
        types = {t["type"]: t for t in out["types"]}
        assert types["PAY_FOR_EQUIPMENT"]["count"] == 3
        assert types["PAY_FOR_EQUIPMENT"]["trend"] == "RISING"
        assert len(out["types"]) <= 4
        assert stats_handler.handler({"queryStringParameters": {"range": "year"}}, None)["statusCode"] == 400
