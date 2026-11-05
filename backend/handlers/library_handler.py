"""Scam library (public, read-only):

GET  /library?type=TASK_SCAMS&cursor=...  past scam messages people chose to share (personal details removed)
GET  /library/sites                       scam websites reported by at least SITE_MIN_REPORTS people
POST /lookup  {contactType, contact}      has this exact email / phone / website been reported?

Emails and phone numbers are never listed publicly: a spoofed or mistyped address could
wrongly brand a real person. They can only be checked one at a time by someone who already has them.
"""
import base64
import json

from hireguard.contacts import CONTACT_TYPES, contact_hash
from hireguard.scam_types import PRIORITY

from .common import BadRequest, log_event, parse_json_body, response, table

PAGE_SIZE = 20
SITE_MIN_REPORTS = 3
TYPE_FILTERS = set(PRIORITY) | {"OTHER"}


def _encode(key: dict | None) -> str | None:
    return base64.urlsafe_b64encode(json.dumps(key).encode()).decode() if key else None


def _decode(cursor: str) -> dict:
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        if not isinstance(key, dict) or set(key) - {"entryId", "kind", "createdAt"}:
            raise ValueError
        return key
    except (ValueError, json.JSONDecodeError) as exc:
        raise BadRequest("Bad cursor.") from exc


def _public_entry(item: dict) -> dict:
    return {
        "id": item["entryId"],
        "createdAt": item["createdAt"],
        "scamType": item.get("scamType", "OTHER"),
        "label": item.get("label"),
        "score": int(item.get("score", 0)),
        "flagIds": item.get("flagIds", []),
        "claimedCompany": item.get("claimedCompany", ""),
        "platform": item.get("platform", ""),
        "text": item.get("text", ""),
    }


def list_library(params: dict) -> dict:
    scam_type = (params.get("type") or "").upper()
    if scam_type and scam_type not in TYPE_FILTERS:
        raise BadRequest("Unknown scam type.")
    kwargs = {
        "IndexName": "byNewest",
        "KeyConditionExpression": "#k = :k",
        "ExpressionAttributeNames": {"#k": "kind"},
        "ExpressionAttributeValues": {":k": "SCAM"},
        "ScanIndexForward": False,
        "Limit": PAGE_SIZE,
    }
    if scam_type:
        kwargs["FilterExpression"] = "#st = :st"
        kwargs["ExpressionAttributeNames"]["#st"] = "scamType"
        kwargs["ExpressionAttributeValues"][":st"] = scam_type
        kwargs["Limit"] = PAGE_SIZE * 5  # the filter runs after the limit
    if params.get("cursor"):
        kwargs["ExclusiveStartKey"] = _decode(params["cursor"])
    page = table("LIBRARY_TABLE").query(**kwargs)
    items = [_public_entry(i) for i in page.get("Items", [])][:PAGE_SIZE]
    return {"items": items, "cursor": _encode(page.get("LastEvaluatedKey"))}


def list_sites() -> dict:
    reports = table("REPORTS_TABLE")
    kwargs = {
        "FilterExpression": "#t = :domain AND #c >= :min AND attribute_exists(#d)",
        "ProjectionExpression": "#d, #c, #l, #cc",
        "ExpressionAttributeNames": {"#t": "contactType", "#c": "reportCount", "#d": "displayDomain",
                                     "#l": "lastReportedAt", "#cc": "claimedCompanies"},
        "ExpressionAttributeValues": {":domain": "DOMAIN", ":min": SITE_MIN_REPORTS},
    }
    sites = []
    while True:
        page = reports.scan(**kwargs)
        sites += page.get("Items", [])
        if "LastEvaluatedKey" not in page or len(sites) >= 500:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    sites.sort(key=lambda s: (int(s["reportCount"]), s.get("lastReportedAt", "")), reverse=True)
    return {
        "minReports": SITE_MIN_REPORTS,
        "sites": [
            {
                "domain": s["displayDomain"],
                "reportCount": int(s["reportCount"]),
                "lastReportedAt": s.get("lastReportedAt"),
                "claimedCompanies": sorted(s.get("claimedCompanies", []))[:5],
            }
            for s in sites[:50]
        ],
    }


def lookup(body: dict) -> dict:
    ctype = body.get("contactType")
    contact = body.get("contact")
    if ctype not in CONTACT_TYPES or not isinstance(contact, str) or not contact.strip() or len(contact) > 320:
        raise BadRequest("Enter an email, phone number or website to check.")
    item = table("REPORTS_TABLE").get_item(Key={"contactHash": contact_hash(ctype, contact)}).get("Item")
    if not item:
        return {"reportCount": 0}
    return {
        "reportCount": int(item["reportCount"]),
        "lastReportedAt": item.get("lastReportedAt"),
        "platforms": sorted(item.get("platforms", [])),
        "claimedCompanies": sorted(item.get("claimedCompanies", []))[:5],
        "lostMoneyCount": int(item.get("lostMoneyCount", 0)),
    }


def handler(event, _context):
    route = event.get("routeKey", "")
    try:
        if route == "GET /library":
            out = list_library(event.get("queryStringParameters") or {})
        elif route == "GET /library/sites":
            out = list_sites()
        elif route == "POST /lookup":
            out = lookup(parse_json_body(event))
        else:
            return response(404, {"error": "Not found."})
    except BadRequest as exc:
        return response(400, {"error": str(exc)})
    log_event("library", route=route)
    resp = response(200, out)
    if route.startswith("GET"):
        resp["headers"]["Cache-Control"] = "public, max-age=60"
    return resp
