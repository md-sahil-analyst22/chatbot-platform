import base64
import os

import pytest

from saathi.platform.errors import ConfigurationError, InfrastructureError, ValidationError
from saathi.platform.security.crypto import AesGcmCipher
from saathi.platform.security.uploads import validate_logo


def _key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def test_round_trip_and_aad_binding() -> None:
    cipher = AesGcmCipher.from_env_value(f"k1:{_key()}")
    token = cipher.encrypt("sk-secret-1234", aad="tenant:a:provider:anthropic")
    assert "sk-secret" not in token
    assert cipher.decrypt(token, aad="tenant:a:provider:anthropic") == "sk-secret-1234"
    with pytest.raises(InfrastructureError):
        cipher.decrypt(token, aad="tenant:b:provider:anthropic")  # copied to another tenant


def test_tampered_token_fails() -> None:
    cipher = AesGcmCipher.from_env_value(f"k1:{_key()}")
    token = cipher.encrypt("x", aad="a")
    with pytest.raises(InfrastructureError):
        cipher.decrypt(token[:-2] + "AA", aad="a")


def test_rotation_keeps_old_tokens_readable() -> None:
    old_key, new_key = _key(), _key()
    old = AesGcmCipher.from_env_value(f"k1:{old_key}")
    token = old.encrypt("secret", aad="a")
    rotated = AesGcmCipher.from_env_value(f"k2:{new_key},k1:{old_key}")
    assert rotated.decrypt(token, aad="a") == "secret"
    assert rotated.needs_rotation(token)
    assert not rotated.needs_rotation(rotated.encrypt("secret", aad="a"))


def test_bad_key_config_fails_fast() -> None:
    with pytest.raises(ConfigurationError):
        AesGcmCipher.from_env_value("k1:" + base64.urlsafe_b64encode(b"short").decode())
    with pytest.raises(ConfigurationError):
        AesGcmCipher.from_env_value("")


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def test_logo_accepts_real_images_only() -> None:
    assert validate_logo(PNG).content_type == "image/png"
    with pytest.raises(ValidationError):
        validate_logo(b"<svg onload='alert(1)'></svg>")
    with pytest.raises(ValidationError):
        validate_logo(PNG + b"0" * 600_000)
    with pytest.raises(ValidationError):
        validate_logo(b"")
