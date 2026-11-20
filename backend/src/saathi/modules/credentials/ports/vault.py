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
    # Lock text, tied to the owner label `aad`.
    def encrypt(self, plaintext: str, *, aad: str) -> str: ...

    # Unlock text; fails if the owner label is different.
    def decrypt(self, token: str, *, aad: str) -> str: ...


# Ask the vendor 'is this key real?' before saving it.
class KeyValidator(Protocol):
    # Ask the vendor whether this key works.
    async def is_valid(self, provider: str, api_key: str) -> bool: ...


# Save and read keys (encrypted) in the database.
class CredentialRepository(Protocol):
    # Save a new key record plus its encrypted key.
    async def add(self, credential: ProviderCredential, ciphertext: str) -> None: ...

    # Save changes to a key record (e.g. revoked).
    async def save(self, credential: ProviderCredential) -> None: ...

    # The active key record + encrypted key for a vendor, or None.
    async def active(
        self, tenant_id: UUID, provider: str
    ) -> tuple[ProviderCredential, str] | None: ...

    # One key record, or None.
    async def get(self, tenant_id: UUID, credential_id: UUID) -> ProviderCredential | None: ...

    # All key records of a tenant.
    async def list_for_tenant(self, tenant_id: UUID) -> list[ProviderCredential]: ...
