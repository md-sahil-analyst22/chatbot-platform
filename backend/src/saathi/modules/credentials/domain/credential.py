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

# Allowed vendor names: 1-30 lowercase letters, digits or '-'.
_PROVIDER = re.compile(r"[a-z0-9-]{1,30}")


# A key is either active or revoked.
class CredentialStatus(StrEnum):
    # In use.
    ACTIVE = "active"
    # Switched off; kept for the record.
    REVOKED = "revoked"


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# One saved key's details (vendor, last 4 characters, status, who added it).
class ProviderCredential:
    # This key record's id.
    id: UUID
    # 🔒 The workspace that owns it.
    tenant_id: UUID
    # The vendor, e.g. 'gemini'.
    provider: str
    # The key's last 4 characters (for display only).
    key_last4: str
    # active or revoked.
    status: CredentialStatus
    # Who added it.
    created_by: str
    # When.
    created_at: datetime

    # Checked automatically when the object is created:
    def __post_init__(self) -> None:
        # the vendor name must look right...
        if not _PROVIDER.fullmatch(self.provider):
            # ...otherwise refuse;
            raise ValidationError("invalid provider name")
        # exactly 4 characters for display...
        if len(self.key_last4) != 4:
            # ...otherwise refuse.
            raise ValidationError("key_last4 must be 4 characters")

    # @property: read it like a field (credential.masked).
    @property
    # Display form, e.g. '••••abcd'.
    def masked(self) -> str:
        # Four dots plus the last 4 characters.
        return f"••••{self.key_last4}"

    # Return a copy marked as revoked.
    def revoked(self) -> "ProviderCredential":
        # Already revoked...
        if self.status is CredentialStatus.REVOKED:
            # ...is a conflict (409).
            raise ConflictError("credential already revoked")
        # A copy marked as revoked.
        return replace(self, status=CredentialStatus.REVOKED)


# 🔒 The 'owner label' bound into the encryption, so a key can't be unlocked for another tenant
# or vendor.
def associated_data(tenant_id: UUID, provider: str) -> str:
    """Binds a ciphertext to exactly one tenant + provider."""
    # e.g. 'tenant:<id>:provider:gemini'.
    return f"tenant:{tenant_id}:provider:{provider}"
