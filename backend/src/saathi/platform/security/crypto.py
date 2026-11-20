# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Locks and unlocks secrets (e.g. tenants' own API keys) with AES-256-GCM encryption.
# Extra protection: Each secret is tied to its owner ('associated data'): a secret copied to
#                   another tenant's row can't be unlocked.
# Key rotation: Several master keys can exist; new secrets use the first, old ones still unlock.
# ─────────────────────────────────────────────────────────────────────────────────────────────
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

# base64 — turns bytes into text and back.
import base64

# os — talks to the operating system (environment variables, files).
import os

# re — regular expressions (text patterns).
import re

# From collections.abc — standard type names for collections: Mapping = type for a read-only
#   dictionary.
from collections.abc import Mapping

# From cryptography.exceptions — errors from the cryptography library: InvalidTag = raised when
#   encrypted data was changed or the key is wrong.
from cryptography.exceptions import InvalidTag

# From cryptography.hazmat.primitives.ciphers.aead — encryption that also detects tampering:
#   AESGCM = AES-256-GCM encryption.
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   InfrastructureError = our side broke.
from saathi.platform.errors import ConfigurationError, InfrastructureError

# Allowed key ids: 1-16 lowercase letters or digits (e.g. 'k1').
_KID = re.compile(r"[a-z0-9]{1,16}")
# Format version written at the start of every locked secret.
_VERSION = "v1"


# Bytes -> text (base64url) so the result can be stored in a text column.
def _b64e(raw: bytes) -> str:
    # Encode to URL-safe base64 and drop the '=' padding.
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


# Text -> bytes (the reverse).
def _b64d(text: str) -> bytes:
    # Add back the '=' padding (to a multiple of 4), then decode.
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# The lock/unlock tool. Master keys come from CREDENTIALS_ENCRYPTION_KEYS in .env.
class AesGcmCipher:
    # `keys` = key id -> 32-byte master key; `current_kid` = the one used for new secrets.
    def __init__(self, keys: Mapping[str, bytes], current_kid: str) -> None:
        # The 'current' key must actually be one of the keys...
        if current_kid not in keys:
            # ...otherwise stop at start-up.
            raise ConfigurationError("current encryption key id is not among the configured keys")
        # Check every key:
        for kid, key in keys.items():
            # the id must look right,
            if not _KID.fullmatch(kid):
                # otherwise stop;
                raise ConfigurationError(f"invalid encryption key id '{kid}'")
            # the key must be exactly 32 bytes (AES-256),
            if len(key) != 32:
                # otherwise stop.
                raise ConfigurationError(f"encryption key '{kid}' must be 32 bytes")
        # Prepare one AES-GCM tool per key.
        self._keys = {kid: AESGCM(key) for kid, key in keys.items()}
        # Remember which key locks new secrets.
        self._current = current_kid

    # A classmethod is called on the class: AesGcmCipher.from_env_value('...').
    @classmethod
    # Read 'k2:<key>,k1:<key>' from the setting; the first key is used for new secrets.
    def from_env_value(cls, value: str) -> "AesGcmCipher":
        # Key id -> key bytes.
        keys: dict[str, bytes] = {}
        # Key ids in the order written (the first one is current).
        order: list[str] = []
        # Go through each non-empty, comma-separated entry...
        for part in (p.strip() for p in value.split(",") if p.strip()):
            # ...and split it at ':' into id and base64 key.
            kid, sep, encoded = part.partition(":")
            # No ':' found:
            if not sep:
                # stop with a message showing the expected format.
                raise ConfigurationError(
                    "CREDENTIALS_ENCRYPTION_KEYS entries must be 'kid:base64key'"
                )
            # Try to decode the key...
            try:
                # ...and store it.
                keys[kid] = _b64d(encoded)
            # Not valid base64:
            except ValueError as exc:
                # stop (the message never includes the key).
                raise ConfigurationError(f"encryption key '{kid}' is not valid base64") from exc
            # Remember the order.
            order.append(kid)
        # No keys at all:
        if not order:
            # stop.
            raise ConfigurationError("CREDENTIALS_ENCRYPTION_KEYS is empty")
        # Build the cipher; the first key is the current one.
        return cls(keys, current_kid=order[0])

    # Lock: a fresh random 'nonce' every time, then encrypt. Result: 'v1.<key
    # id>.<nonce>.<ciphertext>'.
    def encrypt(self, plaintext: str, *, aad: str) -> str:
        # A fresh random 12-byte 'nonce' for every encryption (never reuse one with the same
        #   key).
        nonce = os.urandom(12)
        # Encrypt with the current key, bound to the owner label `aad`.
        ciphertext = self._keys[self._current].encrypt(nonce, plaintext.encode(), aad.encode())
        # Join the parts with dots: v1.<key id>.<nonce>.<ciphertext>.
        return ".".join((_VERSION, self._current, _b64e(nonce), _b64e(ciphertext)))

    # Unlock. Wrong owner, tampering or unknown key -> error that never includes the secret.
    def decrypt(self, token: str, *, aad: str) -> str:
        # Anything wrong below becomes one safe error:
        try:
            # split the stored text into its four parts,
            version, kid, nonce, ciphertext = token.split(".")
            # check the format version,
            if version != _VERSION:
                # unknown version -> treat as invalid,
                raise ValueError("unsupported token version")
            # pick the key that locked it (unknown id -> KeyError),
            aesgcm = self._keys[kid]
            # decrypt; a wrong owner label or any tampering raises InvalidTag.
            return aesgcm.decrypt(_b64d(nonce), _b64d(ciphertext), aad.encode()).decode()
        # Any of those failures:
        except (ValueError, KeyError, InvalidTag) as exc:
            # Never include the token or plaintext in the error.
            raise InfrastructureError("secret could not be decrypted") from exc

    # True if this secret was locked with an older master key.
    def needs_rotation(self, token: str) -> bool:
        # Split into parts.
        parts = token.split(".")
        # Needs re-locking if it's malformed or was locked with an older key.
        return len(parts) != 4 or parts[1] != self._current
