"""Normalise and hash contacts so reports never store the raw email, phone or domain."""
import hashlib
import re

from .email_checks import url_domain

CONTACT_TYPES = ("EMAIL", "PHONE", "DOMAIN")


def normalise_contact(contact_type: str, value: str) -> str:
    value = (value or "").strip().lower()
    if contact_type == "EMAIL":
        return value
    if contact_type == "PHONE":
        digits = re.sub(r"\D", "", value)
        # US numbers: drop a leading country code 1 so "+1 (555) 010-2000" == "555-010-2000"
        return digits[1:] if len(digits) == 11 and digits.startswith("1") else digits
    if contact_type == "DOMAIN":
        return url_domain(value)
    raise ValueError(f"unknown contact type {contact_type}")


def contact_hash(contact_type: str, value: str) -> str:
    norm = normalise_contact(contact_type, value)
    return hashlib.sha256(f"{contact_type}:{norm}".encode()).hexdigest()
