# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Checks that a webhook really came from Meta (WhatsApp) using its secret signature.
# Why: Without this, anyone could send fake messages to our webhook.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Webhook authenticity check (P4.6): X-Hub-Signature-256 = 'sha256=' + HMAC(app_secret, body)."""

import hashlib
import hmac


# Recompute the signature and compare in constant time (no timing leaks).
def is_valid_signature(raw_body: bytes, header_value: str | None, app_secret: str) -> bool:
    """Fail closed: missing/malformed header or empty secret => False."""
    if not header_value or not app_secret or not header_value.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_value.removeprefix("sha256="))
