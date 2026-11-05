from hireguard.redact import redact


def test_removes_contacts_and_links():
    out = redact("Email careers.amazon.hr@gmail.com or text +1 (555) 010-2000. Apply at https://amazon-jobs.net/start or add @amzn_hr_team")
    assert "@gmail.com" not in out and "555" not in out and "amazon-jobs.net" not in out and "amzn_hr_team" not in out
    assert "[email]" in out and "[phone]" in out and "[link]" in out and "[handle]" in out


def test_removes_numbers_names_and_addresses():
    out = redact("Hi Priya,\nSend SSN 123-45-6789 and account 9876543210. Ship to 42 Maple Street.\nRegards, John Smith")
    for secret in ("Priya", "123-45-6789", "9876543210", "Maple", "John Smith"):
        assert secret not in out
    assert out.startswith("Hi [name],")


def test_keeps_company_and_money_words():
    out = redact("Remote Data Entry role at Amazon ($42/hr). Buy the $450 kit from our approved vendor.")
    assert "Amazon" in out and "$42/hr" in out and "$450" in out and "approved vendor" in out


def test_long_text_is_clipped():
    assert len(redact("word " * 1000)) <= 2001
