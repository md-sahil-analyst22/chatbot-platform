# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python description of the usage_logs table: tokens and cost per reply (migration 0002).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""usage_logs table: tokens and cost per LLM call. Created by migration 0002.

Billing history outlives messages: deleting a message (retention) keeps its usage row.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base, created_at, tenant_fk, uuid_pk


# Table `usage_logs`.
class UsageLogRow(Base):
    __tablename__ = "usage_logs"
    __table_args__ = (
        CheckConstraint("key_source IN ('platform', 'tenant')", name="key_source"),
        CheckConstraint("tokens_in >= 0 AND tokens_out >= 0", name="tokens"),
        CheckConstraint("cost_usd >= 0", name="cost"),
        # serves: monthly token-cap check and usage reports for a tenant
        Index("ix_usage_logs_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="SET NULL")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    tokens_in: Mapped[int]
    tokens_out: Mapped[int]
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    key_source: Mapped[str] = mapped_column(String(10))  # whose API key paid
    created_at: Mapped[datetime] = created_at()
