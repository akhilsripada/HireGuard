import pytest

from hireguard.email_checks import check_link_lookalike, check_sender, lookalike_brand, registrable_domain


@pytest.mark.parametrize("sender", [
    "careers.amazon.hr@gmail.com", "amazon.jobs@outlook.com", "x@yahoo.com", "a@icloud.com", "b@proton.me",
])
def test_free_email_claiming_brand(sender):
    ids = [f["id"] for f in check_sender("Job offer from Amazon.", sender)]
    assert "FREE_EMAIL_BIG_BRAND" in ids


def test_company_domain_is_fine():
    assert check_sender("Job offer from Amazon.", "recruiting@amazon.com") == []


def test_linkedin_mention_is_not_impersonation():
    assert check_sender("I found your profile on LinkedIn.", "sam@gmail.com") == []


def test_free_email_hr_without_brand():
    assert [f["id"] for f in check_sender("We are hiring.", "hr.team.hiring@gmail.com")] == ["FREE_EMAIL_HR"]
    assert check_sender("We are hiring.", "christine.smith@gmail.com") == []


@pytest.mark.parametrize("host,brand", [
    ("amaz0n-careers.com", "amazon"),
    ("amazon-jobs-hr.net", "amazon"),
    ("micr0soft-careers.com", "microsoft"),
    ("amazom.com", "amazon"),
    ("deloitte-hiring.net", "deloitte"),
])
def test_lookalike_domains(host, brand):
    assert lookalike_brand(host) == brand


@pytest.mark.parametrize("host", ["amazon.com", "www.amazon.jobs", "careers.google.com", "startups.com", "example.com"])
def test_not_lookalike(host):
    assert lookalike_brand(host) is None


def test_registrable_domain():
    assert registrable_domain("jobs.amazon-hr.net") == "amazon-hr.net"
    assert registrable_domain("careers.example.co.uk") == "example.co.uk"


def test_link_lookalike_flag():
    flag = check_link_lookalike("https://amazon-remote-jobs.net/start")
    assert flag["id"] == "LOOKALIKE_DOMAIN"
    assert "amazon-remote-jobs.net" in flag["evidence"]
