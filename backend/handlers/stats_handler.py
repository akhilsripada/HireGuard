"""GET /stats?range=week|month - which scam types people are running into.

Counts flag types on scans labelled Suspicious or Likely scam, by day, using the
Scans table's `byDay` index. Compares with the previous period to mark trends.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from boto3.dynamodb.conditions import Key

from .common import log_event, response, table

RANGES = {"week": 7, "month": 30}

# Flag IDs grouped into the scam types shown on the Home page
TYPES = {
    "TASK_SCAM": "TASK_SCAMS",
    "PAY_UPFRONT": "PAY_FOR_EQUIPMENT",
    "FAKE_CHECK": "FAKE_CHECK",
    "FREE_EMAIL_BIG_BRAND": "BRAND_IMPERSONATION",
    "LOOKALIKE_DOMAIN": "BRAND_IMPERSONATION",
    "RESHIPPING": "RESHIPPING",
    "GIFT_CARD_CRYPTO": "UNTRACEABLE_PAYMENT",
    "ASKS_SENSITIVE_DATA": "SENSITIVE_DATA",
    "CHAT_APP_INTERVIEW": "CHAT_APP_INTERVIEW",
}


def count_types(start_day: datetime, days: int) -> Counter:
    scans = table("SCANS_TABLE")
    counts: Counter = Counter()
    for i in range(days):
        day = (start_day + timedelta(days=i)).strftime("%Y-%m-%d")
        kwargs = {
            "IndexName": "byDay",
            "KeyConditionExpression": Key("day").eq(day),
            "ProjectionExpression": "flagIds, #lb",
            "ExpressionAttributeNames": {"#lb": "label"},
        }
        while True:
            page = scans.query(**kwargs)
            for item in page.get("Items", []):
                if item.get("label") == "SAFE":
                    continue
                for t in {TYPES[f] for f in item.get("flagIds", []) if f in TYPES}:
                    counts[t] += 1
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return counts


def handler(event, _context):
    rng = ((event.get("queryStringParameters") or {}).get("range") or "week").lower()
    if rng not in RANGES:
        return response(400, {"error": "range must be week or month"})
    days = RANGES[rng]
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    current = count_types(today - timedelta(days=days - 1), days)
    previous = count_types(today - timedelta(days=2 * days - 1), days)
    types = [
        {"type": t, "count": c, "previousCount": previous.get(t, 0), "trend": "RISING" if c > previous.get(t, 0) else "COMMON"}
        for t, c in current.most_common(4)
    ]
    log_event("stats", range=rng, types=len(types))
    resp = response(200, {"range": rng, "types": types})
    resp["headers"]["Cache-Control"] = "public, max-age=300"
    return resp
