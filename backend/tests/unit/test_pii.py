# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Personal data (email, phone, card, Aadhaar, PAN) is masked.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# pytest — the test framework.
import pytest

# From saathi.platform.security.pii — personal-data masking: redact = masks personal data.
from saathi.platform.security.pii import redact


# Run the same test once for each (input, expected output) pair below.
@pytest.mark.parametrize(
    # The names of the two values each case provides.
    ("raw", "expected"),
    # The cases:
    [
        # a PAN number is masked,
        ("My PAN is ABCDE1234F", "My PAN is [PAN]"),
        # an Aadhaar number is masked,
        ("Aadhaar 2345 6789 0123 please", "Aadhaar [AADHAAR] please"),
        # a phone number with +91 is masked,
        ("call +91 98300 12345 now", "call [PHONE] now"),
        # a plain 10-digit mobile number is masked,
        ("call 9830012345", "call [PHONE]"),
        # a card number is masked,
        ("card 4111 1111 1111 1111 ok", "card [CARD] ok"),
        # an email is masked,
        ("mail me at a.b@example.com", "mail me at [EMAIL]"),
        # ordinary numbers are left alone.
        ("Invoice 2024 for 3 items", "Invoice 2024 for 3 items"),
    ],
)
# The test itself (pytest runs every function whose name starts with test_).
def test_redact(raw: str, expected: str) -> None:
    # redact() must turn the input into exactly the expected text.
    assert redact(raw) == expected
