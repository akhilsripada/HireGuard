"""Whole-pipeline tests: the sample set, scoring rules and failure handling."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hireguard import config, scan
from hireguard.contacts import contact_hash
from hireguard.domain_checks import CheckUnavailable

SAMPLES = Path(__file__).parent / "samples"
TODAY = datetime(2026, 11, 3, tzinfo=timezone.utc)
MOCKUP = (
    "Hi! Your resume was selected for a Remote Data Entry Associate role at Amazon ($42/hr). "
    "Interviews are conducted on Telegram - add @amzn_hr_team. Once hired, purchase your home-office kit ($450) "
    "through our approved vendor and you'll be reimbursed with your first check. "
    "Please respond within 2 hours to keep your spot."
)


def load(folder):
    return [json.loads(p.read_text()) for p in sorted((SAMPLES / folder).glob("*.json"))]


def run(sample, **kw):
    return scan(sample["message"], sample["senderEmail"], sample["link"], **kw)


@pytest.mark.parametrize("sample", load("scam"), ids=lambda s: s["id"])
def test_scam_samples(sample):
    r = run(sample)
    ids = {f["id"] for f in r["flags"]}
    assert set(sample["mustFire"]) <= ids
    if sample["expectedLabel"]:
        assert r["label"] == sample["expectedLabel"], r


@pytest.mark.parametrize("sample", load("genuine"), ids=lambda s: s["id"])
def test_genuine_samples(sample):
    r = run(sample)
    assert r["label"] == "SAFE", r


@pytest.mark.parametrize("sample", load("edge"), ids=lambda s: s["id"])
def test_edge_samples_do_not_crash(sample):
    r = run(sample)
    assert 0 <= r["score"] <= 100


def test_success_rates_meet_targets():
    scams = [s for s in load("scam") if s["expectedLabel"] == "LIKELY_SCAM"]
    genuine = load("genuine")
    assert len(scams) >= 15 and len(genuine) >= 15
    scam_ok = sum(run(s)["score"] >= 67 for s in scams) / len(scams)
    genuine_ok = sum(run(s)["score"] <= 33 for s in genuine) / len(genuine)
    assert scam_ok >= 0.9 and genuine_ok >= 0.9


def test_score_capped_and_label_bands():
    r = scan(MOCKUP, "careers.amazon.hr@gmail.com", "https://amazon-remote-jobs.net/start")
    assert r["score"] == 100 and r["label"] == "LIKELY_SCAM"
    assert {"PAY_UPFRONT", "FREE_EMAIL_BIG_BRAND", "CHAT_APP_INTERVIEW"} <= {f["id"] for f in r["flags"]}
    points = [f["points"] for f in r["flags"]]
    assert points == sorted(points, reverse=True)


@pytest.mark.parametrize("score,label", [(0, "SAFE"), (33, "SAFE"), (34, "SUSPICIOUS"), (66, "SUSPICIOUS"), (67, "LIKELY_SCAM")])
def test_label_for(score, label):
    from hireguard import label_for
    assert label_for(score) == label


def test_new_domain_flag():
    r = scan("Apply here.", None, "https://brand-new-jobs.example/apply",
             domain_created_lookup=lambda d: "2026-10-25", today=TODAY)
    flag = next(f for f in r["flags"] if f["id"] == "NEW_DOMAIN")
    assert "9 days ago" in flag["evidence"]


def test_old_domain_no_flag():
    r = scan("Apply here.", None, "https://old.example/apply", domain_created_lookup=lambda d: "2001-01-01", today=TODAY)
    assert r["flags"] == []


def test_external_failures_are_skipped_not_fatal():
    def boom(*_):
        raise CheckUnavailable("timeout")
    r = scan("Apply here.", "hr@company.example", "https://x.example",
             domain_created_lookup=boom, safe_browsing_lookup=boom, reports_lookup=boom, ai_signal=boom)
    assert set(r["checksSkipped"]) == {"domain_age", "safe_browsing", "community_reports", "ai_signal"}
    assert r["label"] == "SAFE"


def test_unsafe_link():
    r = scan("Click to apply.", None, "http://bad.example", safe_browsing_lookup=lambda u: True)
    assert r["flags"][0]["id"] == "UNSAFE_LINK" and r["score"] == config.WEIGHTS["UNSAFE_LINK"]


def test_community_reports_raise_score():
    reported = contact_hash("EMAIL", "Scammer@Gmail.com ")
    r = scan("Hello there, interested in a job?", "scammer@gmail.com", None,
             reports_lookup=lambda h: 4 if h == reported else 0)
    flag = next(f for f in r["flags"] if f["id"] == "COMMUNITY_REPORTED")
    assert r["communityReports"] == 4
    assert flag["points"] == 15 + 3 * 3


def test_ai_signal_points_are_clamped():
    r = scan("Hello.", ai_signal=lambda t: {"id": "AI_SIGNAL", "points": 999, "title": "t", "why": "w", "evidence": "e"})
    assert r["score"] == config.WEIGHTS["AI_SIGNAL_MAX"]
