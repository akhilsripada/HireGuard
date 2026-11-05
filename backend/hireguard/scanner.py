"""The scan pipeline: run every check, add up points, pick a label."""
from datetime import datetime
from typing import Callable, Optional, TypedDict

from . import config
from .contacts import contact_hash
from .domain_checks import domain_age_days
from .email_checks import (
    check_link_lookalike,
    check_sender,
    email_domain,
    is_valid_email,
    registrable_domain,
    url_domain,
)
from .rules import Flag, make_flag, run_text_rules
from .text import prepare

ReportsLookup = Callable[[str], int]               # contact hash -> number of reports
DomainCreatedLookup = Callable[[str], Optional[str]]  # domain -> 'YYYY-MM-DD' or None
SafeBrowsingLookup = Callable[[str], bool]         # url -> unsafe?
AiSignal = Callable[[str], Optional[Flag]]         # message -> optional flag


class ScanResult(TypedDict):
    score: int
    label: str
    flags: list[Flag]
    communityReports: int
    checksSkipped: list[str]


def label_for(score: int) -> str:
    if score <= config.SAFE_MAX:
        return config.LABEL_SAFE
    if score <= config.SUSPICIOUS_MAX:
        return config.LABEL_SUSPICIOUS
    return config.LABEL_SCAM


def _domains_to_age(sender_email: Optional[str], link: Optional[str]) -> list[str]:
    domains = []
    if link:
        host = url_domain(link)
        if host:
            domains.append(registrable_domain(host))
    if sender_email and is_valid_email(sender_email):
        d = email_domain(sender_email)
        if d not in config.FREE_EMAIL_PROVIDERS:
            domains.append(registrable_domain(d))
    return list(dict.fromkeys(domains))


def scan(
    message: str,
    sender_email: Optional[str] = None,
    link: Optional[str] = None,
    *,
    reports_lookup: Optional[ReportsLookup] = None,
    domain_created_lookup: Optional[DomainCreatedLookup] = None,
    safe_browsing_lookup: Optional[SafeBrowsingLookup] = None,
    ai_signal: Optional[AiSignal] = None,
    today: Optional[datetime] = None,
) -> ScanResult:
    text = prepare(message)
    sender_email = (sender_email or "").strip() or None
    link = (link or "").strip() or None
    skipped: list[str] = []
    flags: list[Flag] = []

    # 1. Text rules
    flags += run_text_rules(text)

    # 2. Sender and link (offline)
    flags += check_sender(text, sender_email)
    lookalike_link = check_link_lookalike(link)
    if lookalike_link:
        flags.append(lookalike_link)

    # 3. Domain age (RDAP)
    if domain_created_lookup:
        youngest: Optional[tuple[str, int]] = None
        for domain in _domains_to_age(sender_email, link):
            try:
                created = domain_created_lookup(domain)
            except Exception:  # noqa: BLE001 - any failure means "skip this check"
                if "domain_age" not in skipped:
                    skipped.append("domain_age")
                continue
            if created:
                age = domain_age_days(created, today)
                if youngest is None or age < youngest[1]:
                    youngest = (domain, age)
        if youngest and youngest[1] < config.NEW_DOMAIN_DAYS:
            domain, age = youngest
            flags.append(make_flag(
                "NEW_DOMAIN",
                "Domain was registered very recently",
                "Scam sites are often created days before the messages go out. Real companies' domains are usually years old.",
                f"{domain} · registered {age} day{'s' if age != 1 else ''} ago",
            ))

    # 4. Safe Browsing
    if link and safe_browsing_lookup:
        try:
            if safe_browsing_lookup(link if "://" in link else "https://" + link):
                flags.append(make_flag(
                    "UNSAFE_LINK",
                    "Link is on Google's unsafe-site list",
                    "Google Safe Browsing lists this link as phishing or malware. Don't open it.",
                    link,
                ))
        except Exception:  # noqa: BLE001
            skipped.append("safe_browsing")

    # 5. Community reports
    community = 0
    if reports_lookup:
        hashes = []
        if sender_email and is_valid_email(sender_email):
            hashes.append(contact_hash("EMAIL", sender_email))
            d = email_domain(sender_email)
            if d not in config.FREE_EMAIL_PROVIDERS:
                hashes.append(contact_hash("DOMAIN", d))
        if link and url_domain(link):
            hashes.append(contact_hash("DOMAIN", link))
        try:
            community = max((reports_lookup(h) for h in hashes), default=0)
        except Exception:  # noqa: BLE001
            skipped.append("community_reports")
            community = 0
        if community > 0:
            w = config.WEIGHTS
            pts = min(w["COMMUNITY_REPORTED_MAX"], w["COMMUNITY_REPORTED_BASE"] + w["COMMUNITY_REPORTED_PER_REPORT"] * (community - 1))
            flags.append({
                "id": "COMMUNITY_REPORTED",
                "points": pts,
                "title": "Reported as a scam by other job seekers",
                "why": "Other HireGuard users reported this sender or website as a scam.",
                "evidence": f"Reported {community} time{'s' if community != 1 else ''}",
            })

    # 6. Optional AI signal
    if ai_signal:
        try:
            ai_flag = ai_signal(text)
            if ai_flag:
                ai_flag["points"] = max(0, min(config.WEIGHTS["AI_SIGNAL_MAX"], int(ai_flag["points"])))
                flags.append(ai_flag)
        except Exception:  # noqa: BLE001
            skipped.append("ai_signal")

    # Each rule counts once
    unique: dict[str, Flag] = {}
    for f in flags:
        unique.setdefault(f["id"], f)
    w = config.WEIGHTS
    if len(unique) >= w["MULTIPLE_SIGNS_MIN_FLAGS"]:
        unique["MULTIPLE_SIGNS"] = {
            "id": "MULTIPLE_SIGNS",
            "points": w["MULTIPLE_SIGNS"],
            "title": "Several warning signs together",
            "why": "One sign alone can be innocent. Several different ones in the same message is a strong scam pattern.",
            "evidence": f"{len(unique)} different warning signs in this message",
        }
    final = sorted(unique.values(), key=lambda f: f["points"], reverse=True)

    score = min(config.MAX_SCORE, sum(f["points"] for f in final))
    return {
        "score": score,
        "label": label_for(score),
        "flags": final,
        "communityReports": community,
        "checksSkipped": skipped,
    }
