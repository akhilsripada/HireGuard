"""Sender email and domain checks that need no network."""
import re
from typing import Optional
from urllib.parse import urlparse

from .config import BRANDS, FREE_EMAIL_PROVIDERS
from .rules import Flag, make_flag
from .text import deobfuscate

_EMAIL = re.compile(r"^[A-Za-z0-9._%+'-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")
_TWO_PART_TLDS = {"co.uk", "co.in", "com.au", "co.jp", "com.br", "co.nz", "co.za", "com.mx", "com.sg"}
_SHORT_BRANDS = {b for b in BRANDS if len(b) < 5}  # ups, ibm, meta, uber, nike...
_JOB_SITES = {"linkedin", "indeed"}
_HR_TOKENS = {"hr", "career", "careers", "hiring", "talent", "job", "jobs", "staffing", "payroll",
              "personnel", "team", "dept", "department", "onboarding", "onboard", "recruit", "recruiter",
              "recruiters", "recruiting", "recruitment", "recruits"}


def _looks_like_hr(local: str) -> bool:
    """'careers.amazon.hr' -> True, 'christine' -> False (whole tokens only)."""
    return any(t in _HR_TOKENS for t in re.split(r"[^a-z]+", local.lower()) if t)


def is_valid_email(email: str) -> bool:
    return bool(email) and len(email) <= 254 and bool(_EMAIL.match(email.strip()))


def email_domain(email: str) -> str:
    return email.strip().lower().rsplit("@", 1)[-1]


def url_domain(link: str) -> str:
    link = link.strip()
    if "://" not in link:
        link = "https://" + link
    host = (urlparse(link).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def registrable_domain(host: str) -> str:
    """'jobs.amazon-hr.net' -> 'amazon-hr.net' (good enough without the full public suffix list)."""
    parts = host.lower().strip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_PART_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _is_official(host: str, brand: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in BRANDS[brand])


def _edit_distance_le1(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = sum(x != y for x, y in zip(a, b))
        if diffs == 1:
            return True
        # one adjacent swap ("amzaon")
        idx = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        return len(idx) == 2 and idx[1] == idx[0] + 1 and a[idx[0]] == b[idx[1]] and a[idx[1]] == b[idx[0]]
    if len(a) > len(b):
        a, b = b, a
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            if skipped:
                return False
            skipped = True
            j += 1
        else:
            i += 1
            j += 1
    return True


def lookalike_brand(host: str) -> Optional[str]:
    """Return the brand a domain imitates, or None.

    'amazon-remote-jobs.net' -> 'amazon', 'amaz0n.com' -> 'amazon', 'amazon.com' -> None.
    """
    reg = registrable_domain(host)
    label = deobfuscate(reg.split(".")[0])
    tokens = [t for t in re.split(r"[-_.]", label) if t]
    for brand in BRANDS:
        if _is_official(host, brand):
            return None
    for brand in BRANDS:
        if brand in _SHORT_BRANDS:
            hit = brand in tokens
        else:
            hit = brand in label or any(len(t) >= 5 and _edit_distance_le1(t, brand) for t in tokens)
        if hit:
            return brand
    return None


def brands_mentioned(text: str) -> list[str]:
    """Brands named in the message. Capitalised word required so 'target' or 'apple'
    used as ordinary words don't count."""
    found = []
    for brand in BRANDS:
        if brand in _JOB_SITES:
            continue  # "found your profile on LinkedIn" is normal, not impersonation
        if re.search(r"\b" + brand.capitalize() + r"\b", text) or (
            len(brand) <= 4 and re.search(r"\b" + brand.upper() + r"\b", text)
        ):
            found.append(brand)
    return found


def check_sender(text: str, sender_email: Optional[str]) -> list[Flag]:
    """FREE_EMAIL_BIG_BRAND and LOOKALIKE_DOMAIN for the sender address."""
    if not sender_email or not is_valid_email(sender_email):
        return []
    flags: list[Flag] = []
    domain = email_domain(sender_email)
    local = sender_email.split("@")[0].lower()
    mentioned = brands_mentioned(text)
    in_local = [b for b in BRANDS if b not in _SHORT_BRANDS and b in deobfuscate(local)]
    if domain in FREE_EMAIL_PROVIDERS:
        claimed = mentioned or in_local
        if claimed:
            name = claimed[0].capitalize()
            flags.append(make_flag(
                "FREE_EMAIL_BIG_BRAND",
                "Sender email does not match the company",
                f"The message claims to be from {name} but was sent from a free {domain} address. Big companies email from their own domain.",
                f"{sender_email} → claims \"{name}\"",
            ))
        elif _looks_like_hr(local):
            flags.append(make_flag(
                "FREE_EMAIL_HR",
                "\"HR\" address on a free email service",
                f"Company HR and recruiting teams normally write from the company's own domain, not {domain}.",
                sender_email,
            ))
    else:
        brand = lookalike_brand(domain)
        if brand:
            flags.append(make_flag(
                "LOOKALIKE_DOMAIN",
                "Sender domain imitates a real company",
                f"The sender's domain looks like {brand.capitalize()} but isn't one of its official domains.",
                f"{sender_email} → imitates {BRANDS[brand][0]}",
            ))
    return flags


def check_link_lookalike(link: Optional[str]) -> Optional[Flag]:
    if not link:
        return None
    host = url_domain(link)
    if not host:
        return None
    brand = lookalike_brand(host)
    if not brand:
        return None
    return make_flag(
        "LOOKALIKE_DOMAIN",
        "Link goes to a lookalike domain",
        f"The link's domain looks like {brand.capitalize()} but isn't one of its official domains.",
        f"{host} → imitates {BRANDS[brand][0]}",
    )
