# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts the credentials module needs: encryption, key checking with the vendor,
#       and storage.
# ─────────────────────────────────────────────────────────────────────────────────────────────
from typing import Protocol
from uuid import UUID

from saathi.modules.credentials.domain.credential import ProviderCredential


# Lock/unlock a secret (implemented by platform/security/crypto.py).
class SecretCipher(Protocol):
    def encrypt(self, plaintext: str, *, aad: str) -> str: ...

    def decrypt(self, token: str, *, aad: str) -> str: ...


# Ask the vendor 'is this key real?' before saving it.
class KeyValidator(Protocol):
    async def is_valid(self, provider: str, api_key: str) -> bool: ...


# Save and read keys (encrypted) in the database.
class CredentialRepository(Protocol):
    async def add(self, credential: ProviderCredential, ciphertext: str) -> None: ...

    async def save(self, credential: ProviderCredential) -> None: ...

    async def active(
        self, tenant_id: UUID, provider: str
    ) -> tuple[ProviderCredential, str] | None: ...

    async def get(self, tenant_id: UUID, credential_id: UUID) -> ProviderCredential | None: ...

    async def list_for_tenant(self, tenant_id: UUID) -> list[ProviderCredential]: ...
