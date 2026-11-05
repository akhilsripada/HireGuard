"""Group rule flags into the scam types people recognise (used by stats and the library)."""

FLAG_TO_TYPE = {
    "TASK_SCAM": "TASK_SCAMS",
    "PAY_UPFRONT": "PAY_FOR_EQUIPMENT",
    "FAKE_CHECK": "FAKE_CHECK",
    "FREE_EMAIL_BIG_BRAND": "BRAND_IMPERSONATION",
    "LOOKALIKE_DOMAIN": "BRAND_IMPERSONATION",
    "RESHIPPING": "RESHIPPING",
    "GIFT_CARD_CRYPTO": "UNTRACEABLE_PAYMENT",
    "ASKS_SENSITIVE_DATA": "SENSITIVE_DATA",
    "CHAT_APP_INTERVIEW": "CHAT_APP_INTERVIEW",
}

# When a message has several, the most specific scheme wins
PRIORITY = [
    "TASK_SCAMS", "RESHIPPING", "FAKE_CHECK", "PAY_FOR_EQUIPMENT", "UNTRACEABLE_PAYMENT",
    "BRAND_IMPERSONATION", "SENSITIVE_DATA", "CHAT_APP_INTERVIEW",
]


def types_for(flag_ids) -> set[str]:
    return {FLAG_TO_TYPE[f] for f in flag_ids if f in FLAG_TO_TYPE}


def main_type(flag_ids) -> str:
    found = types_for(flag_ids)
    for t in PRIORITY:
        if t in found:
            return t
    return "OTHER"
