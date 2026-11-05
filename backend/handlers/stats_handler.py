"""GET /stats?range=week|month - which scam types people are running into.

Counts flag types on scans labelled Suspicious or Likely scam, by day, using the
Scans table's `byDay` index. Compares with the previous period to mark trends.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from hireguard.scam_types import types_for

from .common import log_event, response, table

RANGES = {"week": 7, "month": 30}


def count_types(start_day: datetime, days: int) -> Counter:
    scans = table("SCANS_TABLE")
    counts: Counter = Counter()
    for i in range(days):
        day = (start_day + timedelta(days=i)).strftime("%Y-%m-%d")
        kwargs = {
            "IndexName": "byDay",
            "KeyConditionExpression": "#day = :day",
            "ProjectionExpression": "flagIds, #lb",
            "ExpressionAttributeNames": {"#day": "day", "#lb": "label"},
            "ExpressionAttributeValues": {":day": day},
        }
        while True:
            page = scans.query(**kwargs)
            for item in page.get("Items", []):
                if item.get("label") == "SAFE":
                    continue
                for t in types_for(item.get("flagIds", [])):
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
