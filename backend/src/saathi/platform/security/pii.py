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

# re — regular expressions (text patterns).
import re

# Each pattern finds one kind of personal data; the order matters (cards before Aadhaar).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Emails: something@domain.tld
    ("[EMAIL]", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # Card numbers: 13-19 digits, spaces or dashes allowed.
    ("[CARD]", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")),
    # Aadhaar: 12 digits (first digit 2-9), optionally grouped 4-4-4.
    ("[AADHAAR]", re.compile(r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    # Indian mobile numbers: optional +91 or 0, then 10 digits starting with 6-9.
    ("[PHONE]", re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    # PAN: 5 letters, 4 digits, 1 letter.
    ("[PAN]", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
]


# Replace every match with a label like [PHONE].
def redact(text: str) -> str:
    # For each kind of personal data, in order...
    for token, pattern in _PATTERNS:
        # ...replace every match with its label.
        text = pattern.sub(token, text)
    # Return the masked text.
    return text
