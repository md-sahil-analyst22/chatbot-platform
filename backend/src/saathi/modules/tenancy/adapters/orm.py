# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python descriptions of the tenancy tables: tenants, user_accounts, bots,
#       bot_config_versions, assets, audit_logs.
# Note: The tables themselves are created by migration 0002. These classes let SQLAlchemy read
#       and write them.
# Security: 🔒 Every tenant table has tenant_id and row-level security; unique rules are per
#           tenant.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQLAlchemy tables for the tenancy module. Created by migration 0002 (R25).

Every tenant-owned table has tenant_id NOT NULL, forced RLS (in the migration) and
tenant-scoped unique constraints (R23). Child tables reference parents through composite
(tenant_id, id) foreign keys, so a row can never point at another tenant's bot.
"""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From sqlalchemy — SQLAlchemy, our database toolkit: CheckConstraint = a rule every row must
#   satisfy; ForeignKeyConstraint = multi-column link to another table; Index = a search-speeding
#   index; String = short text column type; UniqueConstraint = 'no two rows may share these
#   values'; text = a raw SQL snippet.
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)

# From sqlalchemy.dialects.postgresql — Postgres-only column types: ARRAY = list column type;
#   JSONB = JSON column type; UUID = UUID column type.
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

# From sqlalchemy.orm — SQLAlchemy's table-class tools: Mapped = type hint for a column;
#   mapped_column = defines one column.
from sqlalchemy.orm import Mapped, mapped_column

# From saathi.platform.db.base — shared building blocks for table classes: Base = parent of
#   every table class; created_at = 'created at' column recipe; tenant_fk = tenant_id column
#   recipe; updated_at = 'updated at' column recipe; uuid_pk = id column recipe.
from saathi.platform.db.base import Base, created_at, tenant_fk, updated_at, uuid_pk


# Table `tenants`: one row per customer workspace.
class TenantRow(Base):
    # The real table name in Postgres.
    __tablename__ = "tenants"
    # Table-wide rules:
    __table_args__ = (
        # plan must be starter, growth or pro;
        CheckConstraint("plan IN ('starter', 'growth', 'pro')", name="plan"),
        # the token cap can't be negative.
        CheckConstraint("monthly_token_cap >= 0", name="monthly_token_cap"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # name: up to 200 characters.
    name: Mapped[str] = mapped_column(String(200))
    # plan: defaults to 'starter'.
    plan: Mapped[str] = mapped_column(String(30), server_default="starter")
    # monthly_token_cap: defaults to 2,000,000 tokens.
    monthly_token_cap: Mapped[int] = mapped_column(server_default="2000000")
    # When the workspace was created.
    created_at: Mapped[datetime] = created_at()


# Table `user_accounts`: which login belongs to which workspace, with which role.
class UserAccountRow(Base):
    """A login (Supabase Auth user) that belongs to a tenant with a role."""

    # The real table name in Postgres.
    __tablename__ = "user_accounts"
    # Table-wide rules:
    __table_args__ = (
        # a login can be in a given workspace only once;
        UniqueConstraint("tenant_id", "auth_user_id", name="uq_user_accounts_tenant_auth_user"),
        # role must be one of the four roles;
        CheckConstraint("role IN ('viewer', 'agent', 'admin', 'owner')", name="role"),
        # serves: login -> membership lookup on every authenticated request (ADR-0007)
        Index("ix_user_accounts_auth_user_id", "auth_user_id"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace (required; deleted with the workspace).
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    auth_user_id: Mapped[str] = mapped_column(String(100))  # JWT "sub"
    # The user's email address.
    email: Mapped[str] = mapped_column(String(320))
    # Their role in this workspace.
    role: Mapped[str] = mapped_column(String(20))
    # When they were added.
    created_at: Mapped[datetime] = created_at()


# Table `bots`: one row per chatbot, with its public widget key.
class BotRow(Base):
    # The real table name in Postgres.
    __tablename__ = "bots"
    # Table-wide rules:
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_bots_tenant_name"),  # per tenant only
        UniqueConstraint("public_key", name="uq_bots_public_key"),  # widget lookup by key
        UniqueConstraint("tenant_id", "id", name="uq_bots_tenant_id_id"),  # composite FK target
        # every bot needs at least one language;
        CheckConstraint("cardinality(languages) >= 1", name="languages"),
        # serves: list bots for a tenant, newest first
        Index("ix_bots_tenant_created", "tenant_id", text("created_at DESC")),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the bot.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # name: up to 100 characters.
    name: Mapped[str] = mapped_column(String(100))
    # persona: up to 2000 characters, empty by default.
    persona: Mapped[str] = mapped_column(String(2000), server_default="")
    # languages: a list such as {en,hi}.
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(10)))
    # public_key: the widget key (pk_...).
    public_key: Mapped[str] = mapped_column(String(80))
    # settings: free-form JSON, {} by default.
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # When it was created.
    created_at: Mapped[datetime] = created_at()
    # When it was last changed.
    updated_at: Mapped[datetime] = updated_at()


# Table `bot_config_versions`: every saved configuration version (JSON).
class BotConfigVersionRow(Base):
    """Append-only configuration history. Exactly one 'published' row per bot (partial index)."""

    # The real table name in Postgres.
    __tablename__ = "bot_config_versions"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 (tenant_id, bot_id) must point at a bot of the SAME tenant; deleting the bot
        #   deletes its versions;
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        # version numbers are unique per bot;
        UniqueConstraint("bot_id", "version", name="uq_bot_config_versions_bot_version"),
        # status must be draft, published or archived;
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status"),
        # versions start at 1;
        CheckConstraint("version >= 1", name="version"),
        # 🔒 at most ONE published version per bot (a 'partial unique index'):
        Index(
            # its name,
            "uq_bot_config_versions_one_published",
            # the column it covers,
            "bot_id",
            # unique,
            unique=True,
            # but only among rows whose status is 'published'.
            postgresql_where=text("status = 'published'"),
        ),
        # serves: Studio "latest draft" and version history for a bot
        Index("ix_bot_config_versions_bot_status_version", "bot_id", "status", "version"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns it.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot it configures.
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # version: 1, 2, 3...
    version: Mapped[int]
    # status: draft / published / archived.
    status: Mapped[str] = mapped_column(String(20))
    # config: the whole BotConfig as JSON.
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # created_by: the user id who saved it.
    created_by: Mapped[str] = mapped_column(String(100))
    # When it was saved.
    created_at: Mapped[datetime] = created_at()


# Table `assets`: uploaded files such as logos.
class AssetRow(Base):
    """Branding files (logos) in object storage; the row stores the key, never the bytes."""

    # The real table name in Postgres.
    __tablename__ = "assets"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 the bot must belong to the same tenant; deleting the bot deletes its files;
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        # each storage path is used only once;
        UniqueConstraint("storage_key", name="uq_assets_storage_key"),
        # files can't be empty;
        CheckConstraint("size_bytes > 0", name="size_bytes"),
        # serves: list a bot's assets
        Index("ix_assets_tenant_bot", "tenant_id", "bot_id"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns it.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot it belongs to.
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(30))  # logo, ...
    storage_key: Mapped[str] = mapped_column(String(500))  # "t/{tenant_id}/..."
    # content_type: e.g. image/png.
    content_type: Mapped[str] = mapped_column(String(100))
    # size_bytes: the file size.
    size_bytes: Mapped[int]
    # When it was uploaded.
    created_at: Mapped[datetime] = created_at()


# Table `audit_logs`: who did what, when.
class AuditLogRow(Base):
    """Who did what. Append-only: the app role may INSERT/SELECT but not UPDATE/DELETE."""

    # The real table name in Postgres.
    __tablename__ = "audit_logs"
    # Table-wide rules:
    __table_args__ = (
        # serves: audit trail for a tenant, newest first
        Index("ix_audit_logs_tenant_at", "tenant_id", text("at DESC")),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace it happened in.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # actor: who did it (user id).
    actor: Mapped[str] = mapped_column(String(100))
    # action: what they did, e.g. 'bot.published'.
    action: Mapped[str] = mapped_column(String(100))
    # target: what it was done to.
    target: Mapped[str] = mapped_column(String(200))
    # details: extra JSON, {} by default.
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # at: when it happened.
    at: Mapped[datetime] = created_at()
