# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python description of the handoffs table: a chat handed to a human agent (migration
#       0002).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""handoffs table (Phase 5 state machine). Created by migration 0002."""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From sqlalchemy — SQLAlchemy, our database toolkit: CheckConstraint = a rule every row must
#   satisfy; ForeignKeyConstraint = multi-column link to another table; Index = a search-speeding
#   index; String = short text column type; Text = long text column type; text = a raw SQL
#   snippet.
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, String, Text, text

# From sqlalchemy.dialects.postgresql — Postgres-only column types: UUID = UUID column type.
from sqlalchemy.dialects.postgresql import UUID

# From sqlalchemy.orm — SQLAlchemy's table-class tools: Mapped = type hint for a column;
#   mapped_column = defines one column.
from sqlalchemy.orm import Mapped, mapped_column

# From saathi.platform.db.base — shared building blocks for table classes: Base = parent of
#   every table class; created_at = 'created at' column recipe; tenant_fk = tenant_id column
#   recipe; uuid_pk = id column recipe.
from saathi.platform.db.base import Base, created_at, tenant_fk, uuid_pk


# Table `handoffs`.
class HandoffRow(Base):
    """Bot -> human escalation. States: requested -> notified -> human -> closed | after_hours."""

    # The real table name in Postgres.
    __tablename__ = "handoffs"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 the conversation must belong to the same tenant; deleting it deletes its handoffs:
        ForeignKeyConstraint(
            # these columns...
            ["tenant_id", "conversation_id"],
            # ...point at these columns,
            ["conversations.tenant_id", "conversations.id"],
            # delete together;
            ondelete="CASCADE",
        ),
        # status must be one of these five values:
        CheckConstraint(
            # the allowed values,
            "status IN ('requested', 'notified', 'human', 'closed', 'after_hours')",
            # the rule's name;
            name="status",
        ),
        # At most one open handoff per conversation.
        Index(
            # its name,
            "uq_handoffs_one_open",
            # the column it covers,
            "conversation_id",
            # unique (at most one open handoff per conversation),
            unique=True,
            # counting only handoffs that are still open;
            postgresql_where=text("status NOT IN ('closed', 'after_hours')"),
        ),
        # serves: agent inbox - open handoffs for a tenant, oldest first
        Index("ix_handoffs_tenant_status_created", "tenant_id", "status", "created_at"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # conversation_id: which conversation.
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # reason: why it was handed over.
    reason: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str | None] = mapped_column(Text)  # AI summary for the agent
    # status: starts as 'requested'.
    status: Mapped[str] = mapped_column(String(20), server_default="requested")
    agent_id: Mapped[str | None] = mapped_column(String(100))  # auth user id of the agent
    # When it was requested.
    created_at: Mapped[datetime] = created_at()
    # When it was resolved (empty until then).
    resolved_at: Mapped[datetime | None]
