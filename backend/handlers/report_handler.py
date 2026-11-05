"""POST /report - a signed-in user reports a scam contact.

Only a SHA-256 hash of the normalised contact is stored.
"""
from datetime import datetime, timezone

from hireguard.contacts import CONTACT_TYPES, contact_hash, normalise_contact
from hireguard.email_checks import is_valid_email, url_domain

from .common import BadRequest, log_event, parse_json_body, response, table

PLATFORMS = ("EMAIL", "TEXT", "LINKEDIN", "JOB_SITE", "CHAT_APP")


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
        report = validate(parse_json_body(event))
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
    expr = "ADD #c :one, #p :p, #m :m SET #t = :t, #l = :l"
    if report["claimedCompany"]:
        names["#cc"] = "claimedCompanies"
        values[":cc"] = {report["claimedCompany"]}
        expr = "ADD #c :one, #p :p, #m :m, #cc :cc SET #t = :t, #l = :l"

    item = table("REPORTS_TABLE").update_item(
        Key={"contactHash": h},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )["Attributes"]
    count = int(item["reportCount"])
    log_event("report", contactType=report["contactType"], platform=report["platform"], reportCount=count)
    return response(200, {"reportCount": count})
