# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Tenants' own API keys: save, revoke, encryption, roles.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# base64 — turns bytes into text and back.
import base64

# os — talks to the operating system (environment variables, files).
import os

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# pytest — the test framework.
import pytest

# From tests.fakes.in_memory — in-memory stand-ins for the database stores:
#   InMemoryCredentialRepository = keys in a dict.
from tests.fakes.in_memory import InMemoryCredentialRepository

# From saathi.modules.credentials.application.services — use cases for tenants' own API keys:
#   CredentialService = the API-key use cases.
from saathi.modules.credentials.application.services import CredentialService

# From saathi.modules.credentials.domain.credential — the saved-API-key business object:
#   CredentialStatus = active or revoked.
from saathi.modules.credentials.domain.credential import CredentialStatus

# From saathi.platform.errors — our error types: AuthorizationError = 403 role not allowed;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import AuthorizationError, ValidationError

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Principal, Role

# From saathi.platform.security.crypto — encryption of secrets: AesGcmCipher = the
#   encrypt/decrypt tool.
from saathi.platform.security.crypto import AesGcmCipher

# A fixed test tenant id.
TENANT = UUID("00000000-0000-0000-0000-0000000000bb")
# A test owner.
OWNER = Principal(user_id="owner", tenant_id=TENANT, role=Role.OWNER)
# A test admin.
ADMIN = Principal(user_id="admin", tenant_id=TENANT, role=Role.ADMIN)
# A fake API key (ends in 'abcd').
KEY = "sk-ant-test-0123456789abcd"


# A fake vendor key checker.
class Validator:
    # Choose whether it says yes or no.
    def __init__(self, ok: bool = True) -> None:
        # Remember.
        self.ok = ok

    # Answer the vendor check.
    async def is_valid(self, provider: str, api_key: str) -> bool:
        # Always the chosen answer.
        return self.ok


# Helper: a service with in-memory storage and a real cipher.
def _service(ok: bool = True) -> tuple[CredentialService, InMemoryCredentialRepository]:
    # In-memory key storage.
    repo = InMemoryCredentialRepository()
    # A real AES-GCM cipher with a random key.
    cipher = AesGcmCipher.from_env_value("k1:" + base64.urlsafe_b64encode(os.urandom(32)).decode())
    # The service and the storage (so tests can look inside).
    return CredentialService(repo=repo, cipher=cipher, validator=Validator(ok)), repo


# Owners can save; the key is stored encrypted and shown masked.
async def test_owner_saves_key_encrypted_and_masked() -> None:
    # A fresh service.
    service, repo = _service()
    # Save the key as the owner.
    cred = await service.save_key(OWNER, "anthropic", KEY)
    # Shown as dots + last 4.
    assert cred.masked == "••••abcd"
    # Look at what was stored...
    _, ciphertext = repo.rows[cred.id]
    # ...the plain key must not appear in it.
    assert KEY not in ciphertext
    # Unlocking gives the original key back.
    assert await service.resolve_api_key(TENANT, "anthropic") == KEY


# Saving a new key revokes the old one.
async def test_new_key_revokes_previous() -> None:
    # A fresh service.
    service, _ = _service()
    # Save a first key.
    first = await service.save_key(OWNER, "anthropic", KEY)
    # Save a second key for the same vendor.
    await service.save_key(OWNER, "anthropic", KEY[:-4] + "wxyz")
    # Statuses of all keys.
    statuses = {c.id: c.status for c in await service.list_keys(ADMIN)}
    # The first is revoked.
    assert statuses[first.id] is CredentialStatus.REVOKED
    # The second one is now used.
    assert await service.resolve_api_key(TENANT, "anthropic") == KEY[:-4] + "wxyz"


# Only owners, and only keys the vendor accepts.
async def test_only_owner_and_valid_keys() -> None:
    # A service whose vendor check always says no.
    service, _ = _service(ok=False)
    # Expect 403...
    with pytest.raises(AuthorizationError):
        # ...when an admin tries.
        await service.save_key(ADMIN, "anthropic", KEY)
    # Expect a ValidationError mentioning 'rejected'...
    with pytest.raises(ValidationError, match="rejected"):
        # ...because the vendor refused the key.
        await service.save_key(OWNER, "anthropic", KEY)
    # Expect a ValidationError...
    with pytest.raises(ValidationError):
        # ...for a key that's too short.
        await service.save_key(OWNER, "anthropic", "short")
