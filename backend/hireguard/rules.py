"""Text rules: each looks for one scam pattern in the message.

A rule returns a Flag dict when it fires, or None. Every rule is a pure function
of the prepared message text so it can be unit tested on its own.
"""
import re
from typing import Callable, Optional, TypedDict

from .config import WEIGHTS
from .text import evidence

_F = re.IGNORECASE
_NEAR = r"[^.\n!?]{0,60}"  # "within the same sentence, close by"


class Flag(TypedDict):
    id: str
    points: int
    title: str
    why: str
    evidence: str


def make_flag(rule_id: str, title: str, why: str, ev: str, points: Optional[int] = None) -> Flag:
    return {
        "id": rule_id,
        "points": WEIGHTS[rule_id] if points is None else points,
        "title": title,
        "why": why,
        "evidence": ev,
    }


def _first_match(text: str, patterns: list[re.Pattern]) -> Optional[re.Match]:
    best = None
    for p in patterns:
        m = p.search(text)
        if m and (best is None or m.start() < best.start()):
            best = m
    return best


def _pattern_rule(rule_id: str, title: str, why: str, patterns: list[str]) -> Callable[[str], Optional[Flag]]:
    compiled = [re.compile(p, _F) for p in patterns]

    def rule(text: str) -> Optional[Flag]:
        m = _first_match(text, compiled)
        if not m:
            return None
        return make_flag(rule_id, title, why, evidence(text, m.start(), m.end()))

    rule.__name__ = rule_id.lower()
    rule.rule_id = rule_id  # type: ignore[attr-defined]
    return rule


pay_upfront = _pattern_rule(
    "PAY_UPFRONT",
    "Asks you to pay before you start",
    "Real employers never ask you to buy equipment, training or software up front, even with a promise of reimbursement.",
    [
        r"\b(purchase|buy|pay for|order)\b" + _NEAR + r"\b(equipment|laptop|computer|kit|software|training|starter pack|supplies|licen[cs]e|certification|materials)\b",
        r"\b(training|registration|onboarding|application|processing|activation|background[- ]check|enrol?lment|starter)\s+(fee|charge|cost|deposit)s?\b",
        r"\b(approved|preferred|designated|certified)\s+(vendor|supplier)\b",
        r"\bpay\b" + _NEAR + r"\b(fee|deposit)\b" + _NEAR + r"\b(before|to) (start|begin|get started|secure)\b",
    ],
)

gift_card_crypto = _pattern_rule(
    "GIFT_CARD_CRYPTO",
    "Wants money by gift card, crypto or instant transfer",
    "Gift cards, cryptocurrency and instant transfers can't be traced or refunded, which is why scammers ask for them.",
    [
        r"\b(gift ?cards?|itunes cards?|google play cards?|steam cards?)\b",
        r"\b(bitcoin|btc|usdt|tether|ethereum|crypto(currency)?|crypto wallet|binance|coinbase)\b",
        r"\b(send|transfer|pay|wire)\b" + _NEAR + r"\b(via|by|through|using|with) (zelle|cash ?app|venmo|wire transfer|western union|moneygram)\b",
    ],
)

fake_check = _pattern_rule(
    "FAKE_CHECK",
    "Asks you to deposit a check and send money back",
    "This is a classic fake-check scam: the check bounces days later and you lose the money you sent.",
    [
        r"\b(deposit|cash|mobile deposit)\b" + _NEAR + r"\bche(ck|que)\b" + r"[^.\n!?]{0,100}\b(send|return|transfer|forward|wire|zelle|venmo|cash ?app)\b",
        r"\bsend (back )?the (remaining|rest|balance|difference|excess)\b",
        r"\bwe('ll| will) (send|mail) you a che(ck|que)\b" + r"[^.\n!?]{0,100}\b(purchase|buy|vendor)\b",
    ],
)

asks_sensitive_data = _pattern_rule(
    "ASKS_SENSITIVE_DATA",
    "Asks for sensitive personal or bank details",
    "Your SSN, bank login or ID photos should only go through an employer's official onboarding system after a written offer.",
    [
        r"\b(ssn|social security( number)?)\b",
        r"\b(bank (account|login|details|info(rmation)?|routing)|routing number|account number|online banking (login|password|credentials))\b",
        r"\b(copy|photo|picture|scan|image) of (your |the )?(driver'?s licen[cs]e|passport|id card|state id|credit card|debit card)\b",
    ],
)

task_scam = _pattern_rule(
    "TASK_SCAM",
    "Looks like a \"task\" scam",
    "Jobs that pay you to rate products or boost apps, then ask you to deposit money to unlock earnings, are task scams.",
    [
        r"\b(complete|finish|do)\b[^.\n!?]{0,30}\b\d*\s*(daily |simple |online )?tasks?\b" + r"[^.\n!?]{0,80}\b(commission|earn|unlock|deposit)\b",
        r"\bunlock\b[^.\n!?]{0,40}\b(commission|earnings|salary|account|withdraw)\w*\b",
        r"\b(rat(e|ing)|review(ing)?|lik(e|ing)|boost(ing)?|optimi[sz](e|ing))\b[^.\n!?]{0,30}\b(products?|apps?|videos?|hotels?|data)\b[^.\n!?]{0,60}\b(commission|earn)\w*\b",
        r"\b(top ?up|recharge) (your )?(account|balance)\b",
    ],
)

reshipping = _pattern_rule(
    "RESHIPPING",
    "Asks you to receive and forward packages",
    "\"Reshipping\" jobs use your address to move goods bought with stolen cards, which can get you in legal trouble.",
    [
        r"\b(reship\w*|re-ship\w*|repackag\w*)\b",
        r"\b(receive|accept|collect)\b[^.\n!?]{0,40}\b(packages?|parcels?|shipments?)\b[^.\n!?]{0,80}\b(forward|reship|re-ship|ship them|send them|mail them|label)\w*\b",
        r"\b(package|parcel|shipping|quality)\s+(inspector|handler|forwarding agent|coordinator from home)\b",
    ],
)

chat_app_interview = _pattern_rule(
    "CHAT_APP_INTERVIEW",
    "Interview only over a chat app",
    "Scammers avoid phone or video calls so they can't be identified. Real recruiters schedule calls or video interviews.",
    [
        r"\b(telegram|whatsapp|whats app|signal app|wechat|wickr|google hangouts|kik)\b",
        r"\b(interview|chat|screening)\b[^.\n!?]{0,40}\b(via|over|on|through) (text|chat|sms|instant messag\w*)\b",
    ],
)

no_interview = _pattern_rule(
    "NO_INTERVIEW",
    "Hires you without a real interview",
    "Legitimate employers interview candidates before making an offer.",
    [
        r"\bno interview(s)? (needed|required|necessary)\b",
        r"\bwithout (an? |any )?interview\b",
        r"\b(hired|start) (immediately|today|right away|instantly)\b",
        r"\byou('ve| have) been (hired|selected for the position|offered the position)\b[^.\n!?]{0,60}\b(without|no) (an? )?interview\b",
    ],
)

urgency = _pattern_rule(
    "URGENCY",
    "Pressure to respond fast",
    "Urgency is used to stop you from checking the offer before you act.",
    [
        r"\bwithin (the next )?\d+\s*(hours?|hrs?|minutes?|mins?)\b",
        r"\b(respond|reply|act|confirm|answer)\b[^.\n!?]{0,20}\b(now|immediately|asap|right away|today)\b",
        r"\blimited (spots|positions|slots|openings|seats)\b",
        r"\b(only|just) \d+ (spots|positions|slots|openings) (left|remaining|available)\b",
        r"\boffer (expires|ends) (today|tonight|soon|in \d+)\b",
    ],
)

_LOW_SKILL = re.compile(
    r"\b(data entry|no experience|part[- ]time|from home|remote assistant|virtual assistant|personal assistant|"
    r"simple tasks?|flexible hours|typing|online tasks?|package|parcel|mystery shopper)\b",
    _F,
)
_HOURLY = re.compile(r"\$\s?(\d{2,4})(?:\.\d{1,2})?\s*(?:/|per|an|a)\s*(?:hr|hour)\b", _F)
_DAILY = re.compile(r"\$\s?(\d{3,5})(?:,\d{3})?(?:\.\d{1,2})?\s*(?:/|per|a)\s*day\b", _F)
_WEEKLY = re.compile(r"\$\s?(\d{1,2},?\d{3})(?:\.\d{1,2})?\s*(?:/|per|a)\s*week\b", _F)


def too_good_pay(text: str) -> Optional[Flag]:
    """High pay for low-skill or no-experience work."""
    if not _LOW_SKILL.search(text):
        return None
    for rx, threshold in ((_HOURLY, 35), (_DAILY, 250), (_WEEKLY, 1500)):
        for m in rx.finditer(text):
            amount = int(m.group(1).replace(",", ""))
            if amount >= threshold:
                return make_flag(
                    "TOO_GOOD_PAY",
                    "Pay that's too good for the work",
                    "Very high pay for simple, no-experience work is a common lure.",
                    evidence(text, m.start(), m.end()),
                )
    return None


too_good_pay.rule_id = "TOO_GOOD_PAY"  # type: ignore[attr-defined]

TEXT_RULES: list[Callable[[str], Optional[Flag]]] = [
    pay_upfront,
    gift_card_crypto,
    fake_check,
    asks_sensitive_data,
    task_scam,
    reshipping,
    chat_app_interview,
    no_interview,
    too_good_pay,
    urgency,
]


def run_text_rules(text: str) -> list[Flag]:
    """Run every text rule once and return the flags that fired."""
    flags = []
    for rule in TEXT_RULES:
        flag = rule(text)
        if flag:
            flags.append(flag)
    return flags
