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

TENANT = UUID("00000000-0000-0000-0000-0000000000bb")
OWNER = Principal(user_id="owner", tenant_id=TENANT, role=Role.OWNER)
ADMIN = Principal(user_id="admin", tenant_id=TENANT, role=Role.ADMIN)
KEY = "sk-ant-test-0123456789abcd"


class Validator:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    async def is_valid(self, provider: str, api_key: str) -> bool:
        return self.ok


def _service(ok: bool = True) -> tuple[CredentialService, InMemoryCredentialRepository]:
    repo = InMemoryCredentialRepository()
    cipher = AesGcmCipher.from_env_value("k1:" + base64.urlsafe_b64encode(os.urandom(32)).decode())
    return CredentialService(repo=repo, cipher=cipher, validator=Validator(ok)), repo


async def test_owner_saves_key_encrypted_and_masked() -> None:
    service, repo = _service()
    cred = await service.save_key(OWNER, "anthropic", KEY)
    assert cred.masked == "••••abcd"
    _, ciphertext = repo.rows[cred.id]
    assert KEY not in ciphertext
    assert await service.resolve_api_key(TENANT, "anthropic") == KEY


async def test_new_key_revokes_previous() -> None:
    service, _ = _service()
    first = await service.save_key(OWNER, "anthropic", KEY)
    await service.save_key(OWNER, "anthropic", KEY[:-4] + "wxyz")
    statuses = {c.id: c.status for c in await service.list_keys(ADMIN)}
    assert statuses[first.id] is CredentialStatus.REVOKED
    assert await service.resolve_api_key(TENANT, "anthropic") == KEY[:-4] + "wxyz"


async def test_only_owner_and_valid_keys() -> None:
    service, _ = _service(ok=False)
    with pytest.raises(AuthorizationError):
        await service.save_key(ADMIN, "anthropic", KEY)
    with pytest.raises(ValidationError, match="rejected"):
        await service.save_key(OWNER, "anthropic", KEY)
    with pytest.raises(ValidationError):
        await service.save_key(OWNER, "anthropic", "short")
