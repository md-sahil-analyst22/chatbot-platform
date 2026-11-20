# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python description of the provider_credentials table (encrypted keys).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""provider_credentials table (tenants' own API keys, Phase 8). Created by migration 0002."""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From sqlalchemy — SQLAlchemy, our database toolkit: CheckConstraint = a rule every row must
#   satisfy; Index = a search-speeding index; String = short text column type; Text = long text
#   column type; text = a raw SQL snippet.
from sqlalchemy import CheckConstraint, Index, String, Text, text

# From sqlalchemy.orm — SQLAlchemy's table-class tools: Mapped = type hint for a column;
#   mapped_column = defines one column.
from sqlalchemy.orm import Mapped, mapped_column

# From saathi.platform.db.base — shared building blocks for table classes: Base = parent of
#   every table class; created_at = 'created at' column recipe; tenant_fk = tenant_id column
#   recipe; uuid_pk = id column recipe.
from saathi.platform.db.base import Base, created_at, tenant_fk, uuid_pk


# 🔒 One row per saved key; `ciphertext` is the encrypted key, never plain text.
class ProviderCredentialRow(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked')", name="status"),
        CheckConstraint("char_length(key_last4) = 4", name="key_last4"),
        # At most one active key per tenant + provider; also serves the lookup by provider.
        Index(
            "uq_provider_credentials_one_active",
            "tenant_id",
            "provider",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    provider: Mapped[str] = mapped_column(String(30))
    ciphertext: Mapped[str] = mapped_column(Text)  # AES-GCM token, never the plaintext key
    key_last4: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at()
