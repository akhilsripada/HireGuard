"""Rule weights, score bands and shared constants.

Weights live here so they can be tuned without touching rule code.
"""

MAX_MESSAGE_CHARS = 5000
MIN_MESSAGE_CHARS = 20
MAX_SCORE = 100

# Score bands (inclusive upper bounds)
SAFE_MAX = 33
SUSPICIOUS_MAX = 66

LABEL_SAFE = "SAFE"
LABEL_SUSPICIOUS = "SUSPICIOUS"
LABEL_SCAM = "LIKELY_SCAM"

# Points per rule
# Tuned against tests/samples (v1): a request to move money is near-certain on its own;
# identity mismatches are strong; behaviour signals are weak alone but add up.
WEIGHTS = {
    # Money leaves the job seeker -> near-certain scam on its own
    "PAY_UPFRONT": 60,
    "FAKE_CHECK": 60,
    "RESHIPPING": 60,
    "UNSAFE_LINK": 60,
    "GIFT_CARD_CRYPTO": 50,
    "TASK_SCAM": 50,
    # Identity does not add up
    "FREE_EMAIL_BIG_BRAND": 35,
    "LOOKALIKE_DOMAIN": 35,
    "ASKS_SENSITIVE_DATA": 35,
    # Behaviour signals
    "NEW_DOMAIN": 20,
    "CHAT_APP_INTERVIEW": 20,
    "NO_INTERVIEW": 20,
    "TOO_GOOD_PAY": 20,
    "FREE_EMAIL_HR": 15,
    "URGENCY": 10,
    # Three or more different signs in one message
    "MULTIPLE_SIGNS": 10,
    "MULTIPLE_SIGNS_MIN_FLAGS": 3,
    # Community reports: base + per extra report, capped
    "COMMUNITY_REPORTED_BASE": 15,
    "COMMUNITY_REPORTED_PER_REPORT": 3,
    "COMMUNITY_REPORTED_MAX": 30,
    "AI_SIGNAL_MAX": 10,
}

NEW_DOMAIN_DAYS = 30

FREE_EMAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "msn.com", "yahoo.com", "ymail.com", "aol.com", "icloud.com", "me.com",
    "mail.com", "protonmail.com", "proton.me", "gmx.com", "zoho.com",
    "yandex.com",
}

# Well-known employers people impersonate: brand word -> official domains
BRANDS = {
    "amazon": ["amazon.com", "amazon.jobs", "aws.amazon.com"],
    "google": ["google.com"],
    "microsoft": ["microsoft.com"],
    "apple": ["apple.com"],
    "meta": ["meta.com", "metacareers.com"],
    "facebook": ["facebook.com", "meta.com"],
    "netflix": ["netflix.com"],
    "walmart": ["walmart.com"],
    "target": ["target.com"],
    "fedex": ["fedex.com"],
    "ups": ["ups.com"],
    "dhl": ["dhl.com"],
    "deloitte": ["deloitte.com"],
    "accenture": ["accenture.com"],
    "ibm": ["ibm.com"],
    "oracle": ["oracle.com"],
    "salesforce": ["salesforce.com"],
    "tesla": ["tesla.com"],
    "pfizer": ["pfizer.com"],
    "jpmorgan": ["jpmorgan.com", "jpmorganchase.com"],
    "paypal": ["paypal.com"],
    "linkedin": ["linkedin.com"],
    "indeed": ["indeed.com"],
    "uber": ["uber.com"],
    "airbnb": ["airbnb.com"],
    "costco": ["costco.com"],
    "nike": ["nike.com"],
    "adobe": ["adobe.com"],
    "intel": ["intel.com"],
    "nvidia": ["nvidia.com"],
}

# Characters scammers swap in to make lookalike words
LOOKALIKE_CHARS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s", "@": "a"})
