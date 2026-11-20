# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The use cases for tenants' own API keys: save, list, revoke, and unlock at chat time.
# Security: 🔒 Only owners save or revoke keys. Keys are checked with the vendor, encrypted, and
#           never returned to the browser.
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""BYOK use cases. Plaintext keys exist only inside these methods and are never returned."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from saathi.modules.credentials.domain.credential import (
    CredentialStatus,
    ProviderCredential,
    associated_data,
)
from saathi.modules.credentials.ports.vault import CredentialRepository, KeyValidator, SecretCipher
from saathi.platform.errors import NotFoundError, ValidationError
from saathi.platform.security.auth import Principal, Role, require_role


# Key use cases.
class CredentialService:
    def __init__(
        self,
        *,
        repo: CredentialRepository,
        cipher: SecretCipher,
        validator: KeyValidator,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repo = repo
        self._cipher = cipher
        self._validator = validator
        self._clock = clock

    # Owner only: check format, check with the vendor, revoke the old key, encrypt and save the
    # new one.
    async def save_key(
        self, principal: Principal, provider: str, api_key: str
    ) -> ProviderCredential:
        require_role(principal, Role.OWNER)
        key = api_key.strip()
        if not 20 <= len(key) <= 512 or any(c.isspace() for c in key):
            raise ValidationError("this does not look like a valid API key")
        if not await self._validator.is_valid(provider, key):
            raise ValidationError("the provider rejected this API key")
        # Only one active key per vendor: the previous one is revoked.
        existing = await self._repo.active(principal.tenant_id, provider)
        if existing is not None:
            await self._repo.save(existing[0].revoked())
        credential = ProviderCredential(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            provider=provider,
            key_last4=key[-4:],
            status=CredentialStatus.ACTIVE,
            created_by=principal.user_id,
            created_at=self._clock(),
        )
        # 🔒 Encrypt, tied to this tenant + vendor.
        ciphertext = self._cipher.encrypt(key, aad=associated_data(principal.tenant_id, provider))
        await self._repo.add(credential, ciphertext)
        return credential

    # Admins see masked keys only.
    async def list_keys(self, principal: Principal) -> list[ProviderCredential]:
        require_role(principal, Role.ADMIN)
        return await self._repo.list_for_tenant(principal.tenant_id)

    # Owner only. Another tenant's key id -> 404.
    async def revoke(self, principal: Principal, credential_id: UUID) -> ProviderCredential:
        require_role(principal, Role.OWNER)
        credential = await self._repo.get(principal.tenant_id, credential_id)
        if credential is None:
            raise NotFoundError("credential not found")
        revoked = credential.revoked()
        await self._repo.save(revoked)
        return revoked

    # Unlock the active key when a chat needs it (None if there isn't one).
    async def resolve_api_key(self, tenant_id: UUID, provider: str) -> str | None:
        """Used by the LLM resolver at request time (Phase 8 wiring in bootstrap)."""
        found = await self._repo.active(tenant_id, provider)
        if found is None:
            return None
        _, ciphertext = found
        return self._cipher.decrypt(ciphertext, aad=associated_data(tenant_id, provider))
