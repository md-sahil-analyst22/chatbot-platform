# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 WhatsApp webhook signatures: valid accepted, missing or wrong refused.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# hashlib — fingerprints (hashes) such as SHA-256.
import hashlib

# hmac — signatures made with a shared secret, and safe comparison.
import hmac

# From saathi.modules.channels.adapters.whatsapp.signature — WhatsApp webhook signature check:
#   is_valid_signature = checks a WhatsApp webhook signature.
from saathi.modules.channels.adapters.whatsapp.signature import is_valid_signature

# A test secret.
SECRET = "app-secret"
# A test request body.
BODY = b'{"entry":[]}'
# The correct signature for that body and secret.
GOOD = "sha256=" + hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()


# The correct signature is accepted.
def test_valid_signature() -> None:
    # Must be True.
    assert is_valid_signature(BODY, GOOD, SECRET)


# A changed body is refused.
def test_tampered_body_rejected() -> None:
    # Different body, old signature -> must be False.
    assert not is_valid_signature(b'{"entry":[1]}', GOOD, SECRET)


# Missing pieces always mean 'not valid'.
def test_missing_header_or_secret_fails_closed() -> None:
    # No signature header -> False.
    assert not is_valid_signature(BODY, None, SECRET)
    # No secret configured -> False.
    assert not is_valid_signature(BODY, GOOD, "")
    # Wrong signature format -> False.
    assert not is_valid_signature(BODY, "md5=abc", SECRET)
