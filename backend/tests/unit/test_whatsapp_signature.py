# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 WhatsApp webhook signatures: valid accepted, missing or wrong refused.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
import hashlib
import hmac

from saathi.modules.channels.adapters.whatsapp.signature import is_valid_signature

SECRET = "app-secret"
BODY = b'{"entry":[]}'
GOOD = "sha256=" + hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()


def test_valid_signature() -> None:
    assert is_valid_signature(BODY, GOOD, SECRET)


def test_tampered_body_rejected() -> None:
    assert not is_valid_signature(b'{"entry":[1]}', GOOD, SECRET)


def test_missing_header_or_secret_fails_closed() -> None:
    assert not is_valid_signature(BODY, None, SECRET)
    assert not is_valid_signature(BODY, GOOD, "")
    assert not is_valid_signature(BODY, "md5=abc", SECRET)
