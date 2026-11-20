# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Python descriptions of the knowledge tables: sources, chunks (with vectors) and FAQs.
# Note: Created by migration 0002. The vector column has 1,536 numbers (Gemini embeddings).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQLAlchemy tables for the knowledge module (sources, chunks, FAQs). Created by migration 0002.

Embedding size is fixed platform-wide (R13): gemini-embedding-2 shortened to 1,536 dimensions.
"""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From pgvector.sqlalchemy — pgvector support for SQLAlchemy (embedding columns): Vector = a
#   column type holding an embedding vector.
from pgvector.sqlalchemy import Vector

# From sqlalchemy — SQLAlchemy, our database toolkit: CheckConstraint = a rule every row must
#   satisfy; Computed = a column the database calculates; ForeignKeyConstraint = multi-column link
#   to another table; Index = a search-speeding index; String = short text column type; Text =
#   long text column type; UniqueConstraint = 'no two rows may share these values'; text = a raw
#   SQL snippet.
from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)

# From sqlalchemy.dialects.postgresql — Postgres-only column types: JSONB = JSON column type;
#   TSVECTOR = full-text-search column type; UUID = UUID column type.
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

# From sqlalchemy.orm — SQLAlchemy's table-class tools: Mapped = type hint for a column;
#   mapped_column = defines one column.
from sqlalchemy.orm import Mapped, mapped_column

# From saathi.platform.db.base — shared building blocks for table classes: Base = parent of
#   every table class; created_at = 'created at' column recipe; tenant_fk = tenant_id column
#   recipe; updated_at = 'updated at' column recipe; uuid_pk = id column recipe.
from saathi.platform.db.base import Base, created_at, tenant_fk, updated_at, uuid_pk

# Numbers per embedding vector (must match the embedder, R13).
EMBEDDING_DIMENSIONS = 1536


# Table `sources`: one uploaded file or crawled URL.
class SourceRow(Base):
    """A document or URL a bot learns from. Lifecycle: queued -> processing -> ready | failed."""

    # The real table name in Postgres.
    __tablename__ = "sources"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 (tenant_id, bot_id) must point at a bot of the SAME tenant; deleting the bot
        #   deletes these rows;
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("tenant_id", "id", name="uq_sources_tenant_id_id"),  # composite FK target
        # the same file/URL only once per bot;
        UniqueConstraint("tenant_id", "bot_id", "uri", name="uq_sources_tenant_bot_uri"),
        # kind must be file or url;
        CheckConstraint("kind IN ('file', 'url')", name="kind"),
        # status must be one of the four states;
        CheckConstraint("status IN ('queued', 'processing', 'ready', 'failed')", name="status"),
        # serves: list a bot's sources, newest first
        Index("ix_sources_tenant_bot_created", "tenant_id", "bot_id", text("created_at DESC")),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot learns from it.
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # kind: file or url.
    kind: Mapped[str] = mapped_column(String(10))
    uri: Mapped[str] = mapped_column(String(2000))  # storage key or https URL
    # title: optional display name.
    title: Mapped[str | None] = mapped_column(String(300))
    # status: starts as 'queued'.
    status: Mapped[str] = mapped_column(String(20), server_default="queued")
    content_hash: Mapped[str | None] = mapped_column(String(64))  # sha256: skip unchanged files
    error: Mapped[str | None] = mapped_column(String(500))  # safe summary, never a stack trace
    # synced_at: when it was last processed (empty until then).
    synced_at: Mapped[datetime | None]
    # When it was added.
    created_at: Mapped[datetime] = created_at()
    # When it last changed.
    updated_at: Mapped[datetime] = updated_at()


# Table `chunks`: small pieces of a source, each with its embedding vector for search.
class ChunkRow(Base):
    """A searchable passage: vector (semantic) + tsvector (keyword) for hybrid retrieval."""

    # The real table name in Postgres.
    __tablename__ = "chunks"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 the source must belong to the same tenant; deleting the source deletes its chunks;
        ForeignKeyConstraint(
            ["tenant_id", "source_id"], ["sources.tenant_id", "sources.id"], ondelete="CASCADE"
        ),
        # 🔒 (tenant_id, bot_id) must point at a bot of the SAME tenant; deleting the bot
        #   deletes these rows;
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        # re-ingesting a source replaces its chunks by position (idempotent, R33)
        UniqueConstraint("source_id", "chunk_index", name="uq_chunks_source_index"),
        # chunk numbers start at 0;
        CheckConstraint("chunk_index >= 0", name="chunk_index"),
        # serves: semantic search (cosine distance)
        Index(
            # its name,
            "ix_chunks_embedding_hnsw",
            # the vector column,
            "embedding",
            # an HNSW index (fast 'find the most similar vectors' search),
            postgresql_using="hnsw",
            # compared by cosine similarity;
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # serves: keyword search half of hybrid retrieval
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        # serves: restrict retrieval to one bot's chunks
        Index("ix_chunks_tenant_bot", "tenant_id", "bot_id"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot.
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # source_id: which document it came from.
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # chunk_index: its position in the document (0, 1, 2...).
    chunk_index: Mapped[int]
    # content: the chunk's text.
    content: Mapped[str] = mapped_column(Text)
    # embedding: its vector (1536 numbers).
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    # 'simple' config: no language-specific stemming, so Bengali/Hindi/English all work.
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', content)", persisted=True)
    )
    # metadata: extra JSON (page, heading...), {} by default; named metadata_ in Python
    #   because 'metadata' is reserved.
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    # When it was created.
    created_at: Mapped[datetime] = created_at()


# Table `faqs`: hand-written question/answer pairs.
class FaqRow(Base):
    # The real table name in Postgres.
    __tablename__ = "faqs"
    # Table-wide rules:
    __table_args__ = (
        # 🔒 (tenant_id, bot_id) must point at a bot of the SAME tenant; deleting the bot
        #   deletes these rows;
        ForeignKeyConstraint(
            ["tenant_id", "bot_id"], ["bots.tenant_id", "bots.id"], ondelete="CASCADE"
        ),
        # serves: list / match a bot's FAQs
        Index("ix_faqs_tenant_bot", "tenant_id", "bot_id"),
    )

    # id: random UUID primary key.
    id: Mapped[uuid.UUID] = uuid_pk()
    # 🔒 tenant_id: which workspace owns the row.
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    # bot_id: which bot.
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # question: up to 1000 characters.
    question: Mapped[str] = mapped_column(String(1000))
    # answer: up to 4000 characters.
    answer: Mapped[str] = mapped_column(String(4000))
    # is_active: switched on by default.
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    # When it was created.
    created_at: Mapped[datetime] = created_at()
    # When it last changed.
    updated_at: Mapped[datetime] = updated_at()
