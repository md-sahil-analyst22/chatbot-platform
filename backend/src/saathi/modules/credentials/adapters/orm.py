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
    # The real table name in Postgres.
    __tablename__ = "provider_credentials"
    # Table-wide rules:
    __table_args__ = (
        # status must be active or revoked;
        CheckConstraint("status IN ('active', 'revoked')", name="status"),
        # key_last4 must be exactly 4 characters;
        CheckConstraint("char_length(key_last4) = 4", name="key_last4"),
        # At most one active key per tenant + provider; also serves the lookup by provider.
        Index(
            # its name,
            "uq_provider_credentials_one_active",
            # first column: tenant,
            "tenant_id",
            # second column: vendor,
            "provider",
            # unique,
            unique=True,
            # but only among active keys (so one active key per tenant + vendor).
            postgresql_where=text("status = 'active'"),
        ),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the key.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # provider: the vendor name.
    provider: Mapped[str] = mapped_column(String(30))
    ciphertext: Mapped[str] = mapped_column(Text)  # AES-GCM token, never the plaintext key
    # key_last4: for display.
    key_last4: Mapped[str] = mapped_column(String(4))
    # status: active / revoked.
    status: Mapped[str] = mapped_column(String(20))
    # created_by: who added it.
    created_by: Mapped[str] = mapped_column(String(100))
    # When it was added.
    created_at: Mapped[datetime] = created_at()
