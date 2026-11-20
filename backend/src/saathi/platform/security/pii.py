# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Masks personal data in text before it's logged: emails, card numbers, Aadhaar, Indian
#       phone numbers, PAN.
# Rule: Better to mask too much than too little.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""PII redaction for logs and LLM traces (Aadhaar, PAN, card, Indian phone, email).

Order matters: card numbers are masked before Aadhaar so a 16-digit card is not half-matched.
Over-masking is acceptable; under-masking is not.
"""

import re

# Each pattern finds one kind of personal data; the order matters (cards before Aadhaar).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[EMAIL]", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("[CARD]", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")),
    ("[AADHAAR]", re.compile(r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("[PHONE]", re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("[PAN]", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
]


# Replace every match with a label like [PHONE].
def redact(text: str) -> str:
    for token, pattern in _PATTERNS:
        text = pattern.sub(token, text)
    return text
