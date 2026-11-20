# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts the credentials module needs: encryption, key checking with the vendor,
#       and storage.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.credentials.domain.credential — the saved-API-key business object:
#   ProviderCredential = one saved key's details.
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
