# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python descriptions of the chat tables: contacts, conversations and messages (migration
#       0002).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQLAlchemy tables for the conversation module. Created by migration 0002.

contacts / messages hold personal data (phone, email, message text): never log them (R18), and
delete them through the retention / delete-my-data flow (P6.9).
"""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From sqlalchemy — SQLAlchemy, our database toolkit: CheckConstraint = a rule every row must
#   satisfy; ForeignKey = link to a row in another table; ForeignKeyConstraint = multi-column link
#   to another table; Index = a search-speeding index; SmallInteger = small whole-number column
#   type; String = short text column type; Text = long text column type; UniqueConstraint = 'no
#   two rows may share these values'; text = a raw SQL snippet.
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


# Table `contacts`: a customer who chatted (web visitor or WhatsApp number).
class ContactRow(Base):
    """An end user of a tenant's bot (website visitor or WhatsApp number)."""

    # The real table name in Postgres.
    __tablename__ = "contacts"
    # Table-wide rules:
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_contacts_tenant_id_id"),  # composite FK target
        # serves: find the contact for an inbound WhatsApp number / known email
        Index(
            # its name,
            "uq_contacts_tenant_phone",
            # first column: tenant,
            "tenant_id",
            # second column: phone,
            "phone",
            # unique (one contact per phone number per tenant),
            unique=True,
            # but only where a phone number is set;
            postgresql_where=text("phone IS NOT NULL"),
        ),
        # the same for email:
        Index(
            # its name,
            "uq_contacts_tenant_email",
            # first column: tenant,
            "tenant_id",
            # second column: email,
            "email",
            # unique,
            unique=True,
            # but only where an email is set.
            postgresql_where=text("email IS NOT NULL"),
        ),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164
    # email: optional.
    email: Mapped[str | None] = mapped_column(String(320))
    # name: optional.
    name: Mapped[str | None] = mapped_column(String(200))
    # When first seen.
    created_at: Mapped[datetime] = created_at()
    # When last changed.
    updated_at: Mapped[datetime] = updated_at()


# Table `conversations`: one chat thread and its status.
class ConversationRow(Base):
    # The real table name in Postgres.
    __tablename__ = "conversations"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 (tenant_id, bot_id) must point at a bot of the SAME tenant; deleting the bot
        #   deletes these rows;
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        # (tenant, id) unique, so other tables can link to a conversation of the same tenant;
        UniqueConstraint(
            "tenant_id", "id", name="uq_conversations_tenant_id_id"
        ),  # composite FK target
        # channel must be web, whatsapp or voice;
        CheckConstraint("channel IN ('web', 'whatsapp', 'voice')", name="channel"),
        # status must be open, handed_off or closed;
        CheckConstraint("status IN ('open', 'handed_off', 'closed')", name="status"),
        # satisfaction score, if given, is 1-5;
        CheckConstraint("csat IS NULL OR csat BETWEEN 1 AND 5", name="csat"),
        # serves: Conversations screen - a bot's conversations, most recent activity first
        Index(
            # its name,
            "ix_conversations_tenant_bot_last",
            # tenant,
            "tenant_id",
            # bot,
            "bot_id",
            # most recent first;
            text("last_message_at DESC"),
        ),
        # serves: resume the open conversation for a widget session / WhatsApp number
        Index(
            # its name,
            "ix_conversations_tenant_bot_external_user",
            # tenant,
            "tenant_id",
            # bot,
            "bot_id",
            # the visitor/phone id.
            "external_user_id",
        ),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot answered.
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Kept if the contact is deleted (delete-my-data): the conversation loses its owner link.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    # channel: web / whatsapp / voice.
    channel: Mapped[str] = mapped_column(String(20))
    external_user_id: Mapped[str] = mapped_column(String(100))  # widget session id / phone
    # status: starts as 'open'.
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    outcome: Mapped[str | None] = mapped_column(String(30))  # resolved, unanswered, lead, ...
    # csat: satisfaction score 1-5, if the customer gave one.
    csat: Mapped[int | None] = mapped_column(SmallInteger)
    config_version: Mapped[int | None]  # published bot config version that answered
    # language: e.g. 'hi'.
    language: Mapped[str | None] = mapped_column(String(10))
    # When it started.
    started_at: Mapped[datetime] = created_at()
    # When the last message arrived.
    last_message_at: Mapped[datetime] = created_at()
    # When it was closed (empty while open).
    closed_at: Mapped[datetime | None]


# Table `messages`: each message in a conversation.
class MessageRow(Base):
    # The real table name in Postgres.
    __tablename__ = "messages"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 the conversation must belong to the same tenant; deleting it deletes its messages:
        ForeignKeyConstraint(
            # these columns...
            ["tenant_id", "conversation_id"],
            # ...point at these columns,
            ["conversations.tenant_id", "conversations.id"],
            # delete together.
            ondelete="CASCADE",
        ),
        # role: user, assistant, agent or system;
        CheckConstraint("role IN ('user', 'assistant', 'agent', 'system')", name="role"),
        # confidence, if set, is between 0 and 1;
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence"),
        # serves: transcript of a conversation in order
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        # serves: drop duplicate webhook deliveries (P4.7)
        Index(
            # its name,
            "uq_messages_tenant_external_id",
            # tenant,
            "tenant_id",
            # the channel's message id,
            "external_message_id",
            # unique (the same WhatsApp message is never stored twice),
            unique=True,
            # but only where that id is set.
            postgresql_where=text("external_message_id IS NOT NULL"),
        ),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # conversation_id: which conversation.
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # role: who wrote it.
    role: Mapped[str] = mapped_column(String(20))
    # content: the text.
    content: Mapped[str] = mapped_column(Text)
    # citations: sources the answer used, [] by default.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    # confidence: how sure the bot was (0-1), if known.
    confidence: Mapped[float | None]
    # external_message_id: the channel's own message id (for de-duplication).
    external_message_id: Mapped[str | None] = mapped_column(String(200))
    # When it was written.
    created_at: Mapped[datetime] = created_at()


# Table `unanswered_questions`: questions the bot said "I'm not sure" to (P2.14).
class UnansweredQuestionRow(Base):
    """Feeds Bot Studio's 'Unanswered questions' screen (Phase 5). Created by migration 0004."""

    # The real table name in Postgres.
    __tablename__ = "unanswered_questions"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 (tenant_id, bot_id) must point at a bot of the SAME tenant; deleting the bot
        #   deletes these rows;
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        # 🔒 the conversation (if any) must belong to the same tenant; deleting it deletes these
        #   rows too (per-tenant data deletion);
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["conversations.tenant_id", "conversations.id"],
            ondelete="CASCADE",
        ),
        # reason must be one of the known values;
        CheckConstraint(
            "reason IN ('no_results', 'low_confidence', 'unsupported', 'provider_unavailable')",
            name="reason",
        ),
        # serves: Studio list of a bot's unanswered questions (newest first) and the bot-delete
        #   cascade.
        Index("ix_unanswered_tenant_bot_created", "tenant_id", "bot_id", text("created_at DESC")),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot was asked.
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # conversation_id: the chat it came from (NULL outside a chat, e.g. evals).
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # question: the customer's question (bounded).
    question: Mapped[str] = mapped_column(String(2000))
    # language: reply language code.
    language: Mapped[str] = mapped_column(String(10))
    # reason: why the bot wasn't sure.
    reason: Mapped[str] = mapped_column(String(30))
    # top_score: best retrieval score, if any.
    top_score: Mapped[float | None]
    # config_version: published config version used, if known.
    config_version: Mapped[int | None]
    # When it was asked.
    created_at: Mapped[datetime] = created_at()
