# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python description of the usage_logs table: tokens and cost per reply (migration 0002).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""usage_logs table: tokens and cost per LLM call. Created by migration 0002.

Billing history outlives messages: deleting a message (retention) keeps its usage row.
"""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From decimal — exact decimal numbers: Decimal = exact decimal number (money).
from decimal import Decimal

# From sqlalchemy — SQLAlchemy, our database toolkit: CheckConstraint = a rule every row must
#   satisfy; ForeignKey = link to a row in another table; Index = a search-speeding index; Numeric
#   = exact-number column type; String = short text column type.
from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String

# From sqlalchemy.dialects.postgresql — Postgres-only column types: UUID = UUID column type.
from sqlalchemy.dialects.postgresql import UUID

# From sqlalchemy.orm — SQLAlchemy's table-class tools: Mapped = type hint for a column;
#   mapped_column = defines one column.
from sqlalchemy.orm import Mapped, mapped_column

# From saathi.platform.db.base — shared building blocks for table classes: Base = parent of
#   every table class; created_at = 'created at' column recipe; tenant_fk = tenant_id column
#   recipe; uuid_pk = id column recipe.
from saathi.platform.db.base import Base, created_at, tenant_fk, uuid_pk


# Table `usage_logs`.
class UsageLogRow(Base):
    # The real table name in Postgres.
    __tablename__ = "usage_logs"
    # Table-wide rules:
    __table_args__ = (
        # key_source must be platform or tenant;
        CheckConstraint("key_source IN ('platform', 'tenant')", name="key_source"),
        # token counts can't be negative;
        CheckConstraint("tokens_in >= 0 AND tokens_out >= 0", name="tokens"),
        # cost can't be negative;
        CheckConstraint("cost_usd >= 0", name="cost"),
        # serves: monthly token-cap check and usage reports for a tenant
        Index("ix_usage_logs_tenant_created", "tenant_id", "created_at"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot (cleared if the bot is deleted).
    bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="SET NULL")
    )
    # message_id: which reply (cleared if the message is deleted).
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    # provider: the vendor, e.g. 'gemini'.
    provider: Mapped[str] = mapped_column(String(30))
    # model: the vendor's model id.
    model: Mapped[str] = mapped_column(String(100))
    # tokens_in: tokens sent.
    tokens_in: Mapped[int]
    # tokens_out: tokens received.
    tokens_out: Mapped[int]
    # cost_usd: cost in US dollars, exact to 6 decimal places.
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    key_source: Mapped[str] = mapped_column(String(10))  # whose API key paid
    # When it was logged.
    created_at: Mapped[datetime] = created_at()
