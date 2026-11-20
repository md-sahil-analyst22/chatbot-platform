# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Personal data (email, phone, card, Aadhaar, PAN) is masked.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# pytest — the test framework.
import pytest

# From saathi.platform.security.pii — personal-data masking: redact = masks personal data.
from saathi.platform.security.pii import redact


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("My PAN is ABCDE1234F", "My PAN is [PAN]"),
        ("Aadhaar 2345 6789 0123 please", "Aadhaar [AADHAAR] please"),
        ("call +91 98300 12345 now", "call [PHONE] now"),
        ("call 9830012345", "call [PHONE]"),
        ("card 4111 1111 1111 1111 ok", "card [CARD] ok"),
        ("mail me at a.b@example.com", "mail me at [EMAIL]"),
        ("Invoice 2024 for 3 items", "Invoice 2024 for 3 items"),
    ],
)
def test_redact(raw: str, expected: str) -> None:
    assert redact(raw) == expected
