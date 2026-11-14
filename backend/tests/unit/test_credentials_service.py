import base64
import os
from uuid import UUID

import pytest
from tests.fakes.in_memory import InMemoryCredentialRepository

from saathi.modules.credentials.application.services import CredentialService
from saathi.modules.credentials.domain.credential import CredentialStatus
from saathi.platform.errors import AuthorizationError, ValidationError
from saathi.platform.security.auth import Principal, Role
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
