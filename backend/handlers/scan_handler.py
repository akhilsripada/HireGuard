"""POST /scan - score a job message.

The message text is used in memory only. It is never written to DynamoDB or logs.
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3

from hireguard import config, scan
from hireguard.domain_checks import rdap_created_date, safe_browsing_is_unsafe
from hireguard.email_checks import is_valid_email

from .common import FAST, BadRequest, log_event, parse_json_body, response, secret_value, table

TIMEOUT = float(os.environ.get("EXTERNAL_TIMEOUT_S", "1.5"))
SCAN_TTL_DAYS = 90
DOMAIN_CACHE_TTL_DAYS = 7

# Phrases Comprehend may pull out that point to a scam pitch
AI_SUSPICIOUS = (
    "gift card", "bitcoin", "crypto", "wire transfer", "zelle", "telegram", "whatsapp", "commission",
    "deposit", "vendor", "no experience", "work from home", "starter kit", "activation fee",
)


def validate(body: dict) -> tuple[str, Optional[str], Optional[str]]:
    message = body.get("message")
    if not isinstance(message, str) or len(message.strip()) < config.MIN_MESSAGE_CHARS:
        raise BadRequest(f"Paste at least {config.MIN_MESSAGE_CHARS} characters.")
    if len(message) > config.MAX_MESSAGE_CHARS:
        raise BadRequest(f"Messages can be up to {config.MAX_MESSAGE_CHARS:,} characters.")
    sender = body.get("senderEmail") or None
    if sender is not None and (not isinstance(sender, str) or not is_valid_email(sender)):
        raise BadRequest("Enter a valid email address.")
    link = body.get("link") or None
    if link is not None:
        if not isinstance(link, str) or len(link) > 2048 or not link.strip().lower().startswith(("http://", "https://")):
            raise BadRequest("Enter a full link starting with https://")
    return message, sender, link


def reports_lookup(contact_hash: str) -> int:
    item = table("REPORTS_TABLE").get_item(Key={"contactHash": contact_hash}).get("Item")
    return int(item["reportCount"]) if item else 0


def domain_created_lookup(domain: str) -> Optional[str]:
    cache = table("DOMAIN_CACHE_TABLE")
    hit = cache.get_item(Key={"domain": domain}).get("Item")
    if hit:
        return hit.get("createdDate") or None
    created = rdap_created_date(domain, timeout=TIMEOUT)
    expires = int(time.time()) + DOMAIN_CACHE_TTL_DAYS * 86400
    cache.put_item(Item={"domain": domain, "createdDate": created or "", "expiresAt": expires})
    return created


def safe_browsing_lookup_or_none():
    arn = os.environ.get("SAFE_BROWSING_SECRET_ARN")
    if not arn:
        return None
    key = secret_value(arn).get("apiKey")
    if not key or key == "REPLACE_ME":
        return None
    return lambda url: safe_browsing_is_unsafe(url, key, timeout=TIMEOUT)


def ai_signal_or_none():
    if os.environ.get("AI_SIGNAL_ENABLED", "false").lower() != "true":
        return None
    comprehend = boto3.client("comprehend", config=FAST)

    def signal(text: str):
        phrases = comprehend.detect_key_phrases(Text=text[:4500], LanguageCode="en")["KeyPhrases"]
        hits = sorted({p["Text"] for p in phrases if any(s in p["Text"].lower() for s in AI_SUSPICIOUS)})
        if not hits:
            return None
        return {
            "id": "AI_SIGNAL",
            "points": min(config.WEIGHTS["AI_SIGNAL_MAX"], 5 * len(hits)),
            "title": "Language often seen in scam pitches",
            "why": "Amazon Comprehend picked out phrases that often appear in job scams.",
            "evidence": ", ".join(hits[:4]),
        }

    return signal


def save_scan(scan_id: str, result: dict) -> None:
    now = datetime.now(timezone.utc)
    table("SCANS_TABLE").put_item(Item={
        "scanId": scan_id,
        "score": result["score"],
        "label": result["label"],
        "flagIds": [f["id"] for f in result["flags"]],
        "createdAt": now.isoformat(timespec="seconds"),
        "day": now.strftime("%Y-%m-%d"),
        "expiresAt": int((now + timedelta(days=SCAN_TTL_DAYS)).timestamp()),
    })


def handler(event, _context):
    started = time.time()
    try:
        message, sender, link = validate(parse_json_body(event))
    except BadRequest as exc:
        return response(400, {"error": str(exc)})

    try:
        safe_browsing = safe_browsing_lookup_or_none()
    except Exception:  # noqa: BLE001 - a missing secret must not break scanning
        safe_browsing = None

    result = scan(
        message, sender, link,
        reports_lookup=reports_lookup,
        domain_created_lookup=domain_created_lookup,
        safe_browsing_lookup=safe_browsing,
        ai_signal=ai_signal_or_none(),
    )
    scan_id = str(uuid.uuid4())
    try:
        save_scan(scan_id, result)
    except Exception:  # noqa: BLE001 - history is best-effort; the user still gets a result
        result["checksSkipped"].append("history")

    log_event(
        "scan",
        scanId=scan_id,
        score=result["score"],
        label=result["label"],
        flagIds=[f["id"] for f in result["flags"]],
        checksSkipped=result["checksSkipped"],
        durationMs=int((time.time() - started) * 1000),
    )
    return response(200, {"scanId": scan_id, **result})
