# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python description of the leads table: contact details a customer left (migration 0002).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""leads table (Phase 5 lead capture). Created by migration 0002."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base, created_at, tenant_fk, updated_at, uuid_pk


# Table `leads`.
class LeadRow(Base):
    __tablename__ = "leads"
    __table_args__ = (
        # Deleting a contact (delete-my-data) deletes their leads too.
        ForeignKeyConstraint(
            ["tenant_id", "contact_id"], ["contacts.tenant_id", "contacts.id"], ondelete="CASCADE"
        ),
        CheckConstraint("crm_sync_status IN ('pending', 'synced', 'failed')", name="crm_sync"),
        # serves: leads list for a tenant, newest first
        Index("ix_leads_tenant_created", "tenant_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    crm_sync_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
