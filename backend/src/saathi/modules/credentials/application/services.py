# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The use cases for tenants' own API keys: save, list, revoke, and unlock at chat time.
# Security: 🔒 Only owners save or revoke keys. Keys are checked with the vendor, encrypted, and
#           never returned to the browser.
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""BYOK use cases. Plaintext keys exist only inside these methods and are never returned."""

# From collections.abc — standard type names for collections: Callable = type for a function.
from collections.abc import Callable

# From datetime — dates and times: UTC = the UTC time zone; datetime = a date + time value.
from datetime import UTC, datetime

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# From saathi.modules.credentials.domain.credential — the saved-API-key business object:
#   CredentialStatus = active or revoked; ProviderCredential = one saved key's details;
#   associated_data = the owner label bound into encryption.
from saathi.modules.credentials.domain.credential import (
    CredentialStatus,
    ProviderCredential,
    associated_data,
)

# From saathi.modules.credentials.ports.vault — contracts the credentials module needs:
#   CredentialRepository = contract: store keys; KeyValidator = contract: ask the vendor if a key
#   works; SecretCipher = contract: lock/unlock secrets.
from saathi.modules.credentials.ports.vault import CredentialRepository, KeyValidator, SecretCipher

# From saathi.platform.errors — our error types: NotFoundError = 404 not found; ValidationError
#   = 422 invalid input.
from saathi.platform.errors import NotFoundError, ValidationError

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner; require_role = stops with 403 if the role is
#   too low.
from saathi.platform.security.auth import Principal, Role, require_role


# Key use cases.
class CredentialService:
    # Everything the service needs is handed in:
    def __init__(
        self,
        *,
        repo: CredentialRepository,
        # the lock/unlock tool,
        cipher: SecretCipher,
        # the vendor key checker,
        validator: KeyValidator,
        # and a clock (default: now in UTC).
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        # Remember the storage.
        self._repo = repo
        # Remember the lock tool.
        self._cipher = cipher
        # Remember the checker.
        self._validator = validator
        # Remember the clock.
        self._clock = clock

    # Owner only: check format, check with the vendor, revoke the old key, encrypt and save the
    # new one.
    async def save_key(
        self, principal: Principal, provider: str, api_key: str
    ) -> ProviderCredential:
        # 🔒 Owners only.
        require_role(principal, Role.OWNER)
        # Remove spaces around the key.
        key = api_key.strip()
        # 20-512 characters with no spaces inside, or...
        if not 20 <= len(key) <= 512 or any(c.isspace() for c in key):
            # ...refuse (the message never includes the key).
            raise ValidationError("this does not look like a valid API key")
        # Ask the vendor; a rejected key...
        if not await self._validator.is_valid(provider, key):
            # ...is refused.
            raise ValidationError("the provider rejected this API key")
        # Only one active key per vendor: the previous one is revoked.
        existing = await self._repo.active(principal.tenant_id, provider)
        # If one exists...
        if existing is not None:
            # ...save it as revoked.
            await self._repo.save(existing[0].revoked())
        # Build the new key record:
        credential = ProviderCredential(
            # a new id,
            id=uuid4(),
            # 🔒 the caller's tenant,
            tenant_id=principal.tenant_id,
            # the vendor,
            provider=provider,
            # the last 4 characters only,
            key_last4=key[-4:],
            # active,
            status=CredentialStatus.ACTIVE,
            # who added it,
            created_by=principal.user_id,
            # when.
            created_at=self._clock(),
        )
        # 🔒 Encrypt, tied to this tenant + vendor.
        ciphertext = self._cipher.encrypt(key, aad=associated_data(principal.tenant_id, provider))
        # Save the record and the encrypted key.
        await self._repo.add(credential, ciphertext)
        # Return the record (never the key).
        return credential

    # Admins see masked keys only.
    async def list_keys(self, principal: Principal) -> list[ProviderCredential]:
        # 🔒 Admins and owners.
        require_role(principal, Role.ADMIN)
        # All key records (masked) of the caller's tenant.
        return await self._repo.list_for_tenant(principal.tenant_id)

    # Owner only. Another tenant's key id -> 404.
    async def revoke(self, principal: Principal, credential_id: UUID) -> ProviderCredential:
        # 🔒 Owners only.
        require_role(principal, Role.OWNER)
        # Find the record inside the caller's tenant.
        credential = await self._repo.get(principal.tenant_id, credential_id)
        # Not found (or another tenant's):
        if credential is None:
            # 404.
            raise NotFoundError("credential not found")
        # A revoked copy (409 if already revoked).
        revoked = credential.revoked()
        # Save it.
        await self._repo.save(revoked)
        # Return it.
        return revoked

    # Unlock the active key when a chat needs it (None if there isn't one).
    async def resolve_api_key(self, tenant_id: UUID, provider: str) -> str | None:
        """Used by the LLM resolver at request time (Phase 8 wiring in bootstrap)."""
        # The active key for this tenant + vendor.
        found = await self._repo.active(tenant_id, provider)
        # None saved:
        if found is None:
            # None.
            return None
        # Take the encrypted key from the pair.
        _, ciphertext = found
        # 🔒 Unlock it, tied to this tenant + vendor.
        return self._cipher.decrypt(ciphertext, aad=associated_data(tenant_id, provider))
