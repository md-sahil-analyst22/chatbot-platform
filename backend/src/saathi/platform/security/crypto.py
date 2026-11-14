"""Authenticated encryption for tenant secrets (customer API keys, WhatsApp tokens).

AES-256-GCM with key ids so keys can be rotated without downtime:
    token = "v1.<kid>.<nonce>.<ciphertext>"   (base64url parts)

`aad` (associated data) binds a ciphertext to its owner, e.g. "tenant:<id>:provider:anthropic".
A ciphertext copied into another tenant's row fails to decrypt.

Master keys come from the hosting platform's secret store via CREDENTIALS_ENCRYPTION_KEYS:
    "k2:<base64 32 bytes>,k1:<base64 32 bytes>"   (first = current key for new encryptions)
Generate one with:
    python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
"""

import base64
import os
import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from saathi.platform.errors import ConfigurationError, InfrastructureError

_KID = re.compile(r"[a-z0-9]{1,16}")
_VERSION = "v1"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class AesGcmCipher:
    def __init__(self, keys: Mapping[str, bytes], current_kid: str) -> None:
        if current_kid not in keys:
            raise ConfigurationError("current encryption key id is not among the configured keys")
        for kid, key in keys.items():
            if not _KID.fullmatch(kid):
                raise ConfigurationError(f"invalid encryption key id '{kid}'")
            if len(key) != 32:
                raise ConfigurationError(f"encryption key '{kid}' must be 32 bytes")
        self._keys = {kid: AESGCM(key) for kid, key in keys.items()}
        self._current = current_kid

    @classmethod
    def from_env_value(cls, value: str) -> "AesGcmCipher":
        keys: dict[str, bytes] = {}
        order: list[str] = []
        for part in (p.strip() for p in value.split(",") if p.strip()):
            kid, sep, encoded = part.partition(":")
            if not sep:
                raise ConfigurationError(
                    "CREDENTIALS_ENCRYPTION_KEYS entries must be 'kid:base64key'"
                )
            try:
                keys[kid] = _b64d(encoded)
            except ValueError as exc:
                raise ConfigurationError(f"encryption key '{kid}' is not valid base64") from exc
            order.append(kid)
        if not order:
            raise ConfigurationError("CREDENTIALS_ENCRYPTION_KEYS is empty")
        return cls(keys, current_kid=order[0])

    def encrypt(self, plaintext: str, *, aad: str) -> str:
        nonce = os.urandom(12)
        ciphertext = self._keys[self._current].encrypt(nonce, plaintext.encode(), aad.encode())
        return ".".join((_VERSION, self._current, _b64e(nonce), _b64e(ciphertext)))

    def decrypt(self, token: str, *, aad: str) -> str:
        try:
            version, kid, nonce, ciphertext = token.split(".")
            if version != _VERSION:
                raise ValueError("unsupported token version")
            aesgcm = self._keys[kid]
            return aesgcm.decrypt(_b64d(nonce), _b64d(ciphertext), aad.encode()).decode()
        except (ValueError, KeyError, InvalidTag) as exc:
            # Never include the token or plaintext in the error.
            raise InfrastructureError("secret could not be decrypted") from exc

    def needs_rotation(self, token: str) -> bool:
        parts = token.split(".")
        return len(parts) != 4 or parts[1] != self._current
