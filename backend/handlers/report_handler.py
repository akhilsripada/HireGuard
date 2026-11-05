"""POST /report - a signed-in user reports a scam contact.

Only a SHA-256 hash of the normalised contact is stored.
"""
import uuid
from datetime import datetime, timedelta, timezone

from hireguard.contacts import CONTACT_TYPES, contact_hash, normalise_contact
from hireguard.email_checks import is_valid_email, url_domain
from hireguard.redact import redact
from hireguard.scam_types import main_type

from .common import BadRequest, log_event, parse_json_body, response, table

PLATFORMS = ("EMAIL", "TEXT", "LINKEDIN", "JOB_SITE", "CHAT_APP")
LIBRARY_TTL_DAYS = 365


def parse_share(body: dict) -> dict | None:
    """Optional: the reporter agreed to add the scanned message to the public library."""
    share = body.get("share")
    if not share:
        return None
    if not isinstance(share, dict):
        raise BadRequest("Bad share data.")
    message = share.get("message")
    label = share.get("label")
    flags = share.get("flagIds") or []
    if not isinstance(message, str) or len(message.strip()) < 20 or len(message) > 5000:
        raise BadRequest("The message to share must be 20 to 5,000 characters.")
    if label not in ("SUSPICIOUS", "LIKELY_SCAM"):
        return None  # only messages HireGuard flagged go in the library
    if not isinstance(flags, list):
        raise BadRequest("Bad share data.")
    flags = [f for f in flags if isinstance(f, str) and f.isupper() and len(f) <= 40][:20]
    score = share.get("score")
    return {"text": redact(message), "label": label, "flagIds": flags, "score": int(score) if isinstance(score, int) else 0}


def save_to_library(share: dict, report: dict) -> str:
    now = datetime.now(timezone.utc)
    entry_id = str(uuid.uuid4())
    table("LIBRARY_TABLE").put_item(Item={
        "entryId": entry_id,
        "kind": "SCAM",
        "createdAt": now.isoformat(timespec="seconds"),
        "scamType": main_type(share["flagIds"]),
        "label": share["label"],
        "score": share["score"],
        "flagIds": share["flagIds"],
        "claimedCompany": report["claimedCompany"],
        "platform": report["platform"],
        "text": share["text"],
        "expiresAt": int((now + timedelta(days=LIBRARY_TTL_DAYS)).timestamp()),
    })
    return entry_id


def validate(body: dict) -> dict:
    ctype = body.get("contactType")
    if ctype not in CONTACT_TYPES:
        raise BadRequest("Choose what you are reporting: email, phone or website.")
    contact = body.get("contact")
    if not isinstance(contact, str) or not contact.strip() or len(contact) > 320:
        raise BadRequest("Enter the scammer's contact.")
    if ctype == "EMAIL" and not is_valid_email(contact):
        raise BadRequest("Enter a valid email address.")
    if ctype == "PHONE" and not (7 <= len(normalise_contact("PHONE", contact)) <= 15):
        raise BadRequest("Enter a valid phone number.")
    if ctype == "DOMAIN" and "." not in url_domain(contact):
        raise BadRequest("Enter a valid website.")
    platform = body.get("platform") or "EMAIL"
    if platform not in PLATFORMS:
        raise BadRequest("Choose where they contacted you.")
    company = (body.get("claimedCompany") or "").strip()[:80]
    return {
        "contactType": ctype,
        "contact": contact,
        "platform": platform,
        "claimedCompany": company,
        "lostMoney": bool(body.get("lostMoney")),
    }


def handler(event, _context):
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    if not claims.get("sub"):
        return response(401, {"error": "Please sign in to report a scammer."})
    try:
        body = parse_json_body(event)
        report = validate(body)
        share = parse_share(body)
    except BadRequest as exc:
        return response(400, {"error": str(exc)})

    h = contact_hash(report["contactType"], report["contact"])
    names = {"#c": "reportCount", "#t": "contactType", "#l": "lastReportedAt", "#p": "platforms", "#m": "lostMoneyCount"}
    values = {
        ":one": 1,
        ":t": report["contactType"],
        ":l": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ":p": {report["platform"]},
        ":m": 1 if report["lostMoney"] else 0,
    }
    adds = ["#c :one", "#p :p", "#m :m"]
    sets = ["#t = :t", "#l = :l"]
    if report["claimedCompany"]:
        names["#cc"] = "claimedCompanies"
        values[":cc"] = {report["claimedCompany"]}
        adds.append("#cc :cc")
    if report["contactType"] == "DOMAIN":
        # Websites (not people) can be listed publicly once enough reports come in
        names["#d"] = "displayDomain"
        values[":d"] = normalise_contact("DOMAIN", report["contact"])
        sets.append("#d = :d")
    expr = "ADD " + ", ".join(adds) + " SET " + ", ".join(sets)

    item = table("REPORTS_TABLE").update_item(
        Key={"contactHash": h},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )["Attributes"]
    count = int(item["reportCount"])
    shared_id = save_to_library(share, report) if share else None
    log_event("report", contactType=report["contactType"], platform=report["platform"], reportCount=count, shared=bool(shared_id))
    return response(200, {"reportCount": count, "sharedToLibrary": bool(shared_id)})
