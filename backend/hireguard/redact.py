"""Remove personal details from a message before it is shown in the public scam library.

Scam messages contain the scammer's contact details AND often the victim's own
name, phone or address. Anything that could identify a person is replaced with
a placeholder. Company names (what the scammer impersonated) are kept.
"""
import re

_RULES = [
    (re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    (re.compile(r"\bhttps?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|net|org|info|xyz|top|site|online|io|co|us|biz|example)\b(?:/\S*)?", re.I), "[link]"),
    (re.compile(r"(?<!\w)@[A-Za-z0-9_]{3,}"), "[handle]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[number]"),  # SSN shape
    (re.compile(r"(?:\+?1[\s.-]*)?\(?\b\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}\b"), "[phone]"),  # US formats
    (re.compile(r"\+\d[\d\s().-]{7,}\d"), "[phone]"),  # international
    (re.compile(r"\b\d{6,}\b"), "[number]"),  # account / card / routing numbers
    (re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Dr|Drive|Ct|Court)\b\.?"), "[address]"),
    # Greetings with a first name: "Hi Priya," -> "Hi [name],"
    (re.compile(r"\b(Hi|Hello|Dear|Hey)\s+[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\s*,"), r"\1 [name],"),
    # Sign-offs: "Regards, John Smith" -> "Regards, [name]"
    (re.compile(r"\b(Regards|Thanks|Thank you|Best|Sincerely|Cheers),?\s*\n?\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\b"), r"\1, [name]"),
]

MAX_LIBRARY_CHARS = 2000


def redact(text: str) -> str:
    out = (text or "").strip()
    for rx, repl in _RULES:
        out = rx.sub(repl, out)
    if len(out) > MAX_LIBRARY_CHARS:
        out = out[:MAX_LIBRARY_CHARS].rsplit(" ", 1)[0] + "…"
    return out
