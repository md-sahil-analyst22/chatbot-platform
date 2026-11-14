"""provider_credentials table. Imported by migrations/env.py when Phase 8 starts."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base


class ProviderCredentialRow(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        # At most one active key per tenant + provider.
        Index(
            "uq_provider_credentials_one_active",
            "tenant_id",
            "provider",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(30))
    ciphertext: Mapped[str] = mapped_column(Text)  # AES-GCM token, never the plaintext key
    key_last4: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime]
