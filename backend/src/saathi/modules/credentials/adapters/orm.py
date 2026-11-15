"""provider_credentials table (tenants' own API keys, Phase 8). Created by migration 0002."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base, created_at, tenant_fk, uuid_pk


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
