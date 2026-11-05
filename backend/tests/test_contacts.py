from hireguard.contacts import contact_hash, normalise_contact


def test_email_normalised_before_hashing():
    assert contact_hash("EMAIL", " Scam@Gmail.COM ") == contact_hash("EMAIL", "scam@gmail.com")


def test_phone_formats_match():
    assert normalise_contact("PHONE", "+1 (555) 010-2000") == "5550102000"
    assert contact_hash("PHONE", "555.010.2000") == contact_hash("PHONE", "+1 555 010 2000")


def test_domain_from_url():
    assert normalise_contact("DOMAIN", "https://www.Bad-Jobs.example/apply?x=1") == "bad-jobs.example"


def test_types_do_not_collide():
    assert contact_hash("EMAIL", "a@b.com") != contact_hash("DOMAIN", "a@b.com")


def test_hash_is_not_reversible_text():
    h = contact_hash("EMAIL", "scam@gmail.com")
    assert len(h) == 64 and "scam" not in h
