"""A stored provider key. The domain object NEVER holds the plaintext key."""

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from saathi.platform.errors import ConflictError, ValidationError

_PROVIDER = re.compile(r"[a-z0-9-]{1,30}")


class CredentialStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class ProviderCredential:
    id: UUID
    tenant_id: UUID
    provider: str
    key_last4: str
    status: CredentialStatus
    created_by: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not _PROVIDER.fullmatch(self.provider):
            raise ValidationError("invalid provider name")
        if len(self.key_last4) != 4:
            raise ValidationError("key_last4 must be 4 characters")

    @property
    def masked(self) -> str:
        return f"••••{self.key_last4}"

    def revoked(self) -> "ProviderCredential":
        if self.status is CredentialStatus.REVOKED:
            raise ConflictError("credential already revoked")
        return replace(self, status=CredentialStatus.REVOKED)


def associated_data(tenant_id: UUID, provider: str) -> str:
    """Binds a ciphertext to exactly one tenant + provider."""
    return f"tenant:{tenant_id}:provider:{provider}"
