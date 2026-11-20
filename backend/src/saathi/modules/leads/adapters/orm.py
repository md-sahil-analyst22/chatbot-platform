# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python description of the leads table: contact details a customer left (migration 0002).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""leads table (Phase 5 lead capture). Created by migration 0002."""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From sqlalchemy — SQLAlchemy, our database toolkit: CheckConstraint = a rule every row must
#   satisfy; ForeignKey = link to a row in another table; ForeignKeyConstraint = multi-column link
#   to another table; Index = a search-speeding index; String = short text column type; text = a
#   raw SQL snippet.
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, text

# From sqlalchemy.dialects.postgresql — Postgres-only column types: JSONB = JSON column type;
#   UUID = UUID column type.
from sqlalchemy.dialects.postgresql import JSONB, UUID

# From sqlalchemy.orm — SQLAlchemy's table-class tools: Mapped = type hint for a column;
#   mapped_column = defines one column.
from sqlalchemy.orm import Mapped, mapped_column

# From saathi.platform.db.base — shared building blocks for table classes: Base = parent of
#   every table class; created_at = 'created at' column recipe; tenant_fk = tenant_id column
#   recipe; updated_at = 'updated at' column recipe; uuid_pk = id column recipe.
from saathi.platform.db.base import Base, created_at, tenant_fk, updated_at, uuid_pk


# Table `leads`.
class LeadRow(Base):
    # The real table name in Postgres.
    __tablename__ = "leads"
    # Table-wide rules:
    __table_args__ = (
        # Deleting a contact (delete-my-data) deletes their leads too.
        ForeignKeyConstraint(
            ["tenant_id", "contact_id"], ["contacts.tenant_id", "contacts.id"], ondelete="CASCADE"
        ),
        # CRM sync status must be pending, synced or failed;
        CheckConstraint("crm_sync_status IN ('pending', 'synced', 'failed')", name="crm_sync"),
        # serves: leads list for a tenant, newest first
        Index("ix_leads_tenant_created", "tenant_id", text("created_at DESC")),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # contact_id: who the lead is.
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # conversation_id: where it came from (cleared if that conversation is deleted).
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    # fields: what the customer filled in, as JSON.
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # crm_sync_status: starts as 'pending'.
    crm_sync_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    # When it was created.
    created_at: Mapped[datetime] = created_at()
    # When it last changed.
    updated_at: Mapped[datetime] = updated_at()
