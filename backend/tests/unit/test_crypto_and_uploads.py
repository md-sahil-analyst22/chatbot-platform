# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 Encryption (including tamper and wrong-owner cases) and upload checks by real
#                file bytes.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# base64 — turns bytes into text and back.
import base64

# os — talks to the operating system (environment variables, files).
import os

# pytest — the test framework.
import pytest

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   InfrastructureError = our side broke; ValidationError = 422 invalid input.
from saathi.platform.errors import ConfigurationError, InfrastructureError, ValidationError

# From saathi.platform.security.crypto — encryption of secrets: AesGcmCipher = the
#   encrypt/decrypt tool.
from saathi.platform.security.crypto import AesGcmCipher

# From saathi.platform.security.uploads — upload checks by real file bytes: validate_logo =
#   checks a logo upload.
from saathi.platform.security.uploads import validate_logo


# Helper: a random 32-byte key, as base64 text.
def _key() -> str:
    # Make one.
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


# Encrypt/decrypt works, and only for the same owner label.
def test_round_trip_and_aad_binding() -> None:
    # A cipher with one key.
    cipher = AesGcmCipher.from_env_value(f"k1:{_key()}")
    # Encrypt a fake API key for tenant a.
    token = cipher.encrypt("sk-secret-1234", aad="tenant:a:provider:anthropic")
    # The locked text must not contain the secret.
    assert "sk-secret" not in token
    # Unlocking with the same label gives the secret back.
    assert cipher.decrypt(token, aad="tenant:a:provider:anthropic") == "sk-secret-1234"
    # Expect a InfrastructureError from the next line:
    with pytest.raises(InfrastructureError):
        cipher.decrypt(token, aad="tenant:b:provider:anthropic")  # copied to another tenant


# Any change to the locked text is detected.
def test_tampered_token_fails() -> None:
    # A cipher.
    cipher = AesGcmCipher.from_env_value(f"k1:{_key()}")
    # Lock something.
    token = cipher.encrypt("x", aad="a")
    # Expect a InfrastructureError from the next line:
    with pytest.raises(InfrastructureError):
        # Change the last two characters, then try to unlock.
        cipher.decrypt(token[:-2] + "AA", aad="a")


# After adding a new key, old secrets still unlock.
def test_rotation_keeps_old_tokens_readable() -> None:
    # Two random keys.
    old_key, new_key = _key(), _key()
    # A cipher with only the old key.
    old = AesGcmCipher.from_env_value(f"k1:{old_key}")
    # Lock with the old key.
    token = old.encrypt("secret", aad="a")
    # A cipher with the new key first (current) and the old one second.
    rotated = AesGcmCipher.from_env_value(f"k2:{new_key},k1:{old_key}")
    # The old secret still unlocks.
    assert rotated.decrypt(token, aad="a") == "secret"
    # And it's flagged for re-locking.
    assert rotated.needs_rotation(token)
    # A secret locked with the new key is not flagged.
    assert not rotated.needs_rotation(rotated.encrypt("secret", aad="a"))


# Bad key settings stop the app at start-up.
def test_bad_key_config_fails_fast() -> None:
    # Expect a ConfigurationError from the next line:
    with pytest.raises(ConfigurationError):
        # A key that's too short.
        AesGcmCipher.from_env_value("k1:" + base64.urlsafe_b64encode(b"short").decode())
    # Expect a ConfigurationError from the next line:
    with pytest.raises(ConfigurationError):
        # No keys at all.
        AesGcmCipher.from_env_value("")


# A fake PNG: the real PNG signature followed by filler.
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


# Logos are checked by their real bytes.
def test_logo_accepts_real_images_only() -> None:
    # A PNG is accepted and recognised.
    assert validate_logo(PNG).content_type == "image/png"
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # SVG (which can contain scripts) is refused.
        validate_logo(b"<svg onload='alert(1)'></svg>")
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # Over 512 KB is refused.
        validate_logo(PNG + b"0" * 600_000)
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # An empty file is refused.
        validate_logo(b"")
