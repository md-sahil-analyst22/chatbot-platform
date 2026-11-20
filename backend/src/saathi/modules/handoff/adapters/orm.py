# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python description of the handoffs table: a chat handed to a human agent (migration
#       0002).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""handoffs table (Phase 5 state machine). Created by migration 0002."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base, created_at, tenant_fk, uuid_pk


# Table `handoffs`.
class HandoffRow(Base):
    """Bot -> human escalation. States: requested -> notified -> human -> closed | after_hours."""

    __tablename__ = "handoffs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["conversations.tenant_id", "conversations.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('requested', 'notified', 'human', 'closed', 'after_hours')",
            name="status",
        ),
        # At most one open handoff per conversation.
        Index(
            "uq_handoffs_one_open",
            "conversation_id",
            unique=True,
            postgresql_where=text("status NOT IN ('closed', 'after_hours')"),
        ),
        # serves: agent inbox - open handoffs for a tenant, oldest first
        Index("ix_handoffs_tenant_status_created", "tenant_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str | None] = mapped_column(Text)  # AI summary for the agent
    status: Mapped[str] = mapped_column(String(20), server_default="requested")
    agent_id: Mapped[str | None] = mapped_column(String(100))  # auth user id of the agent
    created_at: Mapped[datetime] = created_at()
    resolved_at: Mapped[datetime | None]
