# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts for saving and finding sources, chunks and FAQs.
# 🔒 Every method takes tenant_id and must filter by it, even though the database's row-level
#    security also protects (R15: defence in depth).
# Search: two kinds of chunk search feed 'hybrid search' (P2.10):
#         vector_search  = 'means the same' (embeddings, cosine distance);
#         keyword_search = 'uses the same words' (Postgres full-text search).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Persistence ports for the knowledge module."""

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.knowledge.domain.chunking — chunk value object: Chunk = one passage.
from saathi.modules.knowledge.domain.chunking import Chunk

# From saathi.modules.knowledge.domain.entities — source aggregate: Source = one document/site.
from saathi.modules.knowledge.domain.entities import Source

# From saathi.modules.knowledge.domain.faq — FAQ entity: Faq = one question + exact answer.
from saathi.modules.knowledge.domain.faq import Faq


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after creation.
@dataclass(frozen=True, slots=True)
# A source plus the bookkeeping the list screen shows.
class SourceListing:
    # The source itself.
    source: Source
    # When it was added.
    created_at: datetime
    # When it last finished processing (None until then).
    synced_at: datetime | None
    # How many chunks it currently has.
    chunk_count: int


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after creation.
@dataclass(frozen=True, slots=True)
# One chunk found by a search.
class ChunkHit:
    # The chunk's id (used to merge the two search lists).
    chunk_id: UUID
    # Which source it came from.
    source_id: UUID
    # The source's display title (file name or page title).
    source_title: str
    # The passage text.
    text: str
    # The heading path ('' if none).
    section: str
    # Page number (None for web/plain text).
    page: int | None
    # Web page address (website sources only).
    url: str | None
    # The search's own score (cosine similarity for vectors, rank for keywords).
    score: float


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after creation.
@dataclass(frozen=True, slots=True)
# The closest FAQ to a question.
class FaqMatch:
    # The FAQ.
    faq: Faq
    # Cosine similarity between the question and the FAQ question (1.0 = identical meaning).
    similarity: float


# Contract: store and load sources.
class SourceRepository(Protocol):
    # Save a new source. Raises ConflictError if the bot already has this file/URL.
    async def add(self, source: Source) -> None: ...

    # Load one source, or None (also None for another tenant's source).
    async def get(self, tenant_id: UUID, source_id: UUID) -> Source | None: ...

    # Load a bot's source by its location (storage key or URL), or None.
    async def get_by_uri(self, tenant_id: UUID, bot_id: UUID, uri: str) -> Source | None: ...

    # Load one source and LOCK its row until the transaction ends, so two workers can't
    #   process the same source at the same time.
    async def get_for_update(self, tenant_id: UUID, source_id: UUID) -> Source | None: ...

    # Save the source's status, fingerprint, error and title. synced_at is set when READY.
    #   Raises NotFoundError if the row is gone.
    async def save(self, source: Source) -> None: ...

    # Delete a source and its chunks. True if something was deleted.
    async def delete(self, tenant_id: UUID, source_id: UUID) -> bool: ...

    # A bot's sources, newest first, at most `limit`.
    async def list_for_bot(
        self, tenant_id: UUID, bot_id: UUID, limit: int
    ) -> list[SourceListing]: ...

    # Every source of a bot, locked (used to re-queue them all after a chunking change).
    async def all_for_bot_for_update(self, tenant_id: UUID, bot_id: UUID) -> list[Source]: ...


# Contract: store and search chunks.
class ChunkRepository(Protocol):
    # Replace ALL chunks of a source with these (same transaction as the source update, R26).
    #   `vectors[i]` is the embedding of `chunks[i]`.
    async def replace_for_source(
        self,
        source: Source,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None: ...

    # How many chunks a source has.
    async def count_for_source(self, tenant_id: UUID, source_id: UUID) -> int: ...

    # The `limit` chunks of one bot closest in meaning to the vector.
    async def vector_search(
        self, tenant_id: UUID, bot_id: UUID, vector: Sequence[float], limit: int
    ) -> list[ChunkHit]: ...

    # The `limit` chunks of one bot that best match the words of the query.
    async def keyword_search(
        self, tenant_id: UUID, bot_id: UUID, query: str, limit: int
    ) -> list[ChunkHit]: ...


# Contract: store FAQs and find the closest one.
class FaqRepository(Protocol):
    # Save a new FAQ with its question's embedding.
    async def add(self, faq: Faq, vector: Sequence[float]) -> None: ...

    # Save changes; pass a new vector when the question changed. Raises NotFoundError if gone.
    async def update(self, faq: Faq, vector: Sequence[float] | None) -> None: ...

    # Delete one FAQ. True if something was deleted.
    async def delete(self, tenant_id: UUID, faq_id: UUID) -> bool: ...

    # Load one FAQ, or None.
    async def get(self, tenant_id: UUID, faq_id: UUID) -> Faq | None: ...

    # A bot's FAQs, newest first, at most `limit`.
    async def list_for_bot(self, tenant_id: UUID, bot_id: UUID, limit: int) -> list[Faq]: ...

    # The active FAQ whose question is closest in meaning to the vector, or None.
    async def best_match(
        self, tenant_id: UUID, bot_id: UUID, vector: Sequence[float]
    ) -> FaqMatch | None: ...
