from typing import Protocol
from uuid import UUID

from saathi.modules.credentials.domain.credential import ProviderCredential


class SecretCipher(Protocol):
    def encrypt(self, plaintext: str, *, aad: str) -> str: ...

    def decrypt(self, token: str, *, aad: str) -> str: ...


class KeyValidator(Protocol):
    async def is_valid(self, provider: str, api_key: str) -> bool: ...


class CredentialRepository(Protocol):
    async def add(self, credential: ProviderCredential, ciphertext: str) -> None: ...

    async def save(self, credential: ProviderCredential) -> None: ...

    async def active(
        self, tenant_id: UUID, provider: str
    ) -> tuple[ProviderCredential, str] | None: ...

    async def get(self, tenant_id: UUID, credential_id: UUID) -> ProviderCredential | None: ...

    async def list_for_tenant(self, tenant_id: UUID) -> list[ProviderCredential]: ...
