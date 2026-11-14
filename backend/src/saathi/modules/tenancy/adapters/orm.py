"""SQLAlchemy tables for the tenancy module. Imported by migrations/env.py for autogenerate."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base


class TenantRow(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(30), default="starter")
    monthly_token_cap: Mapped[int] = mapped_column(default=2_000_000)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BotRow(Base):
    __tablename__ = "bots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),  # names unique per tenant, not globally
        UniqueConstraint("public_key"),  # widget lookup by key
        Index("ix_bots_tenant_id_created_at", "tenant_id", "created_at"),  # list bots by tenant
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(100))
    persona: Mapped[str] = mapped_column(String(2000), default="")
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(10)))
    public_key: Mapped[str] = mapped_column(String(80))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BotConfigVersionRow(Base):
    """Append-only configuration history. Exactly one 'published' row per bot (partial index)."""

    __tablename__ = "bot_config_versions"
    __table_args__ = (
        UniqueConstraint("bot_id", "version"),
        Index(
            "uq_bot_config_versions_one_published",
            "bot_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
        # Studio: "latest draft" and "version history" for a bot.
        Index("ix_bot_config_versions_bot_status_version", "bot_id", "status", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE")
    )
    version: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime]
