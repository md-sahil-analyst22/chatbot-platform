# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: A tenant's own API key for an AI vendor ('bring your own key'), as a business object.
# Security: 🔒 The object never holds the key itself - only its last 4 characters for display.
#           The encrypted key lives in the database.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""A stored provider key. The domain object NEVER holds the plaintext key."""

# re — regular expressions (text patterns).
import re

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; replace = copies an object with some fields changed.
from dataclasses import dataclass, replace

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ConflictError, ValidationError

_PROVIDER = re.compile(r"[a-z0-9-]{1,30}")


# A key is either active or revoked.
class CredentialStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
# One saved key's details (vendor, last 4 characters, status, who added it).
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
    # Display form, e.g. '••••abcd'.
    def masked(self) -> str:
        return f"••••{self.key_last4}"

    # Return a copy marked as revoked.
    def revoked(self) -> "ProviderCredential":
        if self.status is CredentialStatus.REVOKED:
            raise ConflictError("credential already revoked")
        return replace(self, status=CredentialStatus.REVOKED)


# 🔒 The 'owner label' bound into the encryption, so a key can't be unlocked for another tenant
# or vendor.
def associated_data(tenant_id: UUID, provider: str) -> str:
    """Binds a ciphertext to exactly one tenant + provider."""
    return f"tenant:{tenant_id}:provider:{provider}"
