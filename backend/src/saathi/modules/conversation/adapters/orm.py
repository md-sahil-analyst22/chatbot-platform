"""SQLAlchemy tables for the conversation module. Created by migration 0002.

contacts / messages hold personal data (phone, email, message text): never log them (R18), and
delete them through the retention / delete-my-data flow (P6.9).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from saathi.platform.db.base import Base, created_at, tenant_fk, updated_at, uuid_pk


class ContactRow(Base):
    """An end user of a tenant's bot (website visitor or WhatsApp number)."""

    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_contacts_tenant_id_id"),  # composite FK target
        # serves: find the contact for an inbound WhatsApp number / known email
        Index(
            "uq_contacts_tenant_phone",
            "tenant_id",
            "phone",
            unique=True,
            postgresql_where=text("phone IS NOT NULL"),
        ),
        Index(
            "uq_contacts_tenant_email",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164
    email: Mapped[str | None] = mapped_column(String(320))
    name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ConversationRow(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        UniqueConstraint(
            "tenant_id", "id", name="uq_conversations_tenant_id_id"
        ),  # composite FK target
        CheckConstraint("channel IN ('web', 'whatsapp', 'voice')", name="channel"),
        CheckConstraint("status IN ('open', 'handed_off', 'closed')", name="status"),
        CheckConstraint("csat IS NULL OR csat BETWEEN 1 AND 5", name="csat"),
        # serves: Conversations screen - a bot's conversations, most recent activity first
        Index(
            "ix_conversations_tenant_bot_last",
            "tenant_id",
            "bot_id",
            text("last_message_at DESC"),
        ),
        # serves: resume the open conversation for a widget session / WhatsApp number
        Index(
            "ix_conversations_tenant_bot_external_user",
            "tenant_id",
            "bot_id",
            "external_user_id",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Kept if the contact is deleted (delete-my-data): the conversation loses its owner link.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(String(20))
    external_user_id: Mapped[str] = mapped_column(String(100))  # widget session id / phone
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    outcome: Mapped[str | None] = mapped_column(String(30))  # resolved, unanswered, lead, ...
    csat: Mapped[int | None] = mapped_column(SmallInteger)
    config_version: Mapped[int | None]  # published bot config version that answered
    language: Mapped[str | None] = mapped_column(String(10))
    started_at: Mapped[datetime] = created_at()
    last_message_at: Mapped[datetime] = created_at()
    closed_at: Mapped[datetime | None]


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["conversations.tenant_id", "conversations.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("role IN ('user', 'assistant', 'agent', 'system')", name="role"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence"),
        # serves: transcript of a conversation in order
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        # serves: drop duplicate webhook deliveries (P4.7)
        Index(
            "uq_messages_tenant_external_id",
            "tenant_id",
            "external_message_id",
            unique=True,
            postgresql_where=text("external_message_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    confidence: Mapped[float | None]
    external_message_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = created_at()
