"""Network checks: domain age (RDAP) and Google Safe Browsing.

Both use only the standard library (no extra packages in the Lambda) and have a
hard timeout. On any failure they raise CheckUnavailable, and the scanner skips
the check and reports it in `checksSkipped` instead of failing the scan.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

RDAP_URL = "https://rdap.org/domain/{domain}"
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find?key={key}"
USER_AGENT = "HireGuard/1.0 (job-scam checker)"


class CheckUnavailable(Exception):
    """The external service could not answer in time."""


def _get_json(url: str, timeout: float, body: Optional[dict] = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URLs)
            return json.loads(resp.read().decode() or "{}")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise CheckUnavailable(str(exc)) from exc


def rdap_created_date(domain: str, timeout: float = 1.5) -> Optional[str]:
    """Return the domain's registration date as 'YYYY-MM-DD', or None if RDAP has none."""
    data = _get_json(RDAP_URL.format(domain=domain), timeout)
    for event in data.get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            return event["eventDate"][:10]
    return None


def domain_age_days(created: str, today: Optional[datetime] = None) -> int:
    today = today or datetime.now(timezone.utc)
    created_dt = datetime.strptime(created, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (today - created_dt).days


def safe_browsing_is_unsafe(url: str, api_key: str, timeout: float = 1.5) -> bool:
    body = {
        "client": {"clientId": "hireguard", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    data = _get_json(SAFE_BROWSING_URL.format(key=api_key), timeout, body)
    return bool(data.get("matches"))
