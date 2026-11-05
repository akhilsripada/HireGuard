"""Each text rule: one message where it must fire, one where it must not."""
import pytest

from hireguard import rules

CASES = [
    (rules.pay_upfront, "Please purchase your laptop from our approved vendor.", "Your laptop will be shipped to you at no cost."),
    (rules.pay_upfront, "There is a $95 training fee before you start.", "Paid training is provided in your first week."),
    (rules.gift_card_crypto, "Buy three Apple gift cards and send photos.", "We offer a gift of company swag on day one."),
    (rules.gift_card_crypto, "Send the balance via Zelle to our supplier.", "Payroll is by direct deposit every two weeks."),
    (rules.fake_check, "Deposit the check and send the remaining balance to the vendor.", "Your first paycheck arrives on the 15th."),
    (rules.asks_sensitive_data, "Reply with your SSN and bank account number.", "Please complete the forms in our HR portal."),
    (rules.task_scam, "Complete 40 tasks to unlock your commission.", "You will complete onboarding tasks in Workday."),
    (rules.reshipping, "Receive parcels at home and reship them with our labels.", "We will ship your welcome kit to your home."),
    (rules.chat_app_interview, "Interviews are done on Telegram.", "Interviews are done on Zoom."),
    (rules.no_interview, "You are hired without an interview.", "The next step is a 30-minute interview."),
    (rules.too_good_pay, "Data entry from home, $45/hr, no experience.", "Senior engineer, $85/hr, 8 years experience."),
    (rules.urgency, "Respond within 2 hours to keep your spot.", "Applications close in two weeks."),
]


@pytest.mark.parametrize("rule,fires,quiet", CASES, ids=[f"{c[0].rule_id}-{i}" for i, c in enumerate(CASES)])
def test_rule_fires_and_stays_quiet(rule, fires, quiet):
    flag = rule(fires)
    assert flag is not None, f"{rule.rule_id} should fire on: {fires}"
    assert flag["id"] == rule.rule_id
    assert flag["points"] > 0 and flag["title"] and flag["why"] and flag["evidence"]
    assert rule(quiet) is None, f"{rule.rule_id} should not fire on: {quiet}"


def test_evidence_quotes_the_sentence():
    flag = rules.urgency("Great news. Please respond within 2 hours to keep your spot. Thanks!")
    assert flag["evidence"] == "Please respond within 2 hours to keep your spot."


def test_each_rule_fires_once_even_with_many_matches():
    flags = rules.run_text_rules("Buy gift cards. More gift cards. Even more gift cards.")
    assert [f["id"] for f in flags].count("GIFT_CARD_CRYPTO") == 1
