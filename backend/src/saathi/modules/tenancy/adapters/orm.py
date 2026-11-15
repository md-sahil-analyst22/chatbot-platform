"""SQLAlchemy tables for the tenancy module. Created by migration 0002 (R25).

Every tenant-owned table has tenant_id NOT NULL, forced RLS (in the migration) and
tenant-scoped unique constraints (R23). Child tables reference parents through composite
(tenant_id, id) foreign keys, so a row can never point at another tenant's bot.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base, created_at, tenant_fk, updated_at, uuid_pk


class TenantRow(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("plan IN ('starter', 'growth', 'pro')", name="plan"),
        CheckConstraint("monthly_token_cap >= 0", name="monthly_token_cap"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(30), server_default="starter")
    monthly_token_cap: Mapped[int] = mapped_column(server_default="2000000")
    created_at: Mapped[datetime] = created_at()


class UserAccountRow(Base):
    """A login (Supabase Auth user) that belongs to a tenant with a role."""

    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "auth_user_id", name="uq_user_accounts_tenant_auth_user"),
        CheckConstraint("role IN ('viewer', 'agent', 'admin', 'owner')", name="role"),
        # serves: login -> membership lookup on every authenticated request (ADR-0007)
        Index("ix_user_accounts_auth_user_id", "auth_user_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    auth_user_id: Mapped[str] = mapped_column(String(100))  # JWT "sub"
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = created_at()


class BotRow(Base):
    __tablename__ = "bots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_bots_tenant_name"),  # per tenant only
        UniqueConstraint("public_key", name="uq_bots_public_key"),  # widget lookup by key
        UniqueConstraint("tenant_id", "id", name="uq_bots_tenant_id_id"),  # composite FK target
        CheckConstraint("cardinality(languages) >= 1", name="languages"),
        # serves: list bots for a tenant, newest first
        Index("ix_bots_tenant_created", "tenant_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    name: Mapped[str] = mapped_column(String(100))
    persona: Mapped[str] = mapped_column(String(2000), server_default="")
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(10)))
    public_key: Mapped[str] = mapped_column(String(80))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class BotConfigVersionRow(Base):
    """Append-only configuration history. Exactly one 'published' row per bot (partial index)."""

    __tablename__ = "bot_config_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("bot_id", "version", name="uq_bot_config_versions_bot_version"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status"),
        CheckConstraint("version >= 1", name="version"),
        Index(
            "uq_bot_config_versions_one_published",
            "bot_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
        # serves: Studio "latest draft" and version history for a bot
        Index("ix_bot_config_versions_bot_status_version", "bot_id", "status", "version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_at()


class AssetRow(Base):
    """Branding files (logos) in object storage; the row stores the key, never the bytes."""

    __tablename__ = "assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("storage_key", name="uq_assets_storage_key"),
        CheckConstraint("size_bytes > 0", name="size_bytes"),
        # serves: list a bot's assets
        Index("ix_assets_tenant_bot", "tenant_id", "bot_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(30))  # logo, ...
    storage_key: Mapped[str] = mapped_column(String(500))  # "t/{tenant_id}/..."
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    created_at: Mapped[datetime] = created_at()


class AuditLogRow(Base):
    """Who did what. Append-only: the app role may INSERT/SELECT but not UPDATE/DELETE."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        # serves: audit trail for a tenant, newest first
        Index("ix_audit_logs_tenant_at", "tenant_id", text("at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    at: Mapped[datetime] = created_at()
