# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Saves chunks and runs the two searches of hybrid retrieval in Postgres
#       (implements ChunkRepository).
# Vector search: ORDER BY cosine distance with pgvector ('<=>'), filtered by tenant + bot.
# Keyword search: Postgres full-text search with the 'simple' configuration (no stemming, so
#   English, Hindi and Bengali are all treated the same way). The question is turned into
#   'word1 | word2 | ...' (any word may match) by Postgres's OWN tokenizer, the same one that
#   built the stored tsv column, so both sides split words identically and user text never
#   becomes query syntax (no injection).
# 🔒 Every query filters by tenant_id AND bot_id (R15) on top of row-level security.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQL chunk repository: replace chunks, vector search, keyword search (P2.7, P2.10)."""

# From collections.abc — standard type names for collections: Sequence = read-only list type.
from collections.abc import Sequence

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = make a new random id.
from uuid import UUID, uuid4

# From sqlalchemy — SQLAlchemy, our database toolkit: delete = DELETE statement; func = SQL
#   functions; insert = INSERT statement; select = SELECT statement; text = a raw SQL snippet.
from sqlalchemy import delete, func, insert, select, text

# From sqlalchemy.ext.asyncio — async database sessions: AsyncSession = one async session.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.modules.knowledge.adapters.orm — knowledge tables: ChunkRow = chunks table.
from saathi.modules.knowledge.adapters.orm import ChunkRow

# From saathi.modules.knowledge.domain.chunking — chunk value object: Chunk = one passage.
from saathi.modules.knowledge.domain.chunking import Chunk

# From saathi.modules.knowledge.domain.entities — sources: Source = one document/site.
from saathi.modules.knowledge.domain.entities import Source

# From saathi.modules.knowledge.ports.repositories — storage contracts: ChunkHit = one found chunk.
from saathi.modules.knowledge.ports.repositories import ChunkHit

# Insert at most this many chunks per statement (keeps each round trip a sensible size).
_INSERT_BATCH = 500
# HNSW search breadth when the planner uses the vector index: higher = better recall, slower.
#   pgvector's default is 40; a filtered search (tenant + bot) needs more candidates.
_EF_SEARCH = 100

# Keyword search. :query is bound as a parameter (never formatted into SQL). strip() drops word
#   positions, the ::text form is "'word1' 'word2'", and replacing the spaces with ' | ' makes
#   "'word1' | 'word2'" -> any word may match. An empty question gives an empty tsquery, which
#   matches nothing.
_KEYWORD_SQL = text(
    """
    WITH q AS (
        SELECT replace(strip(to_tsvector('simple', :query))::text, ' ', ' | ')::tsquery AS tsq
    )
    SELECT c.id, c.source_id, c.content, c.metadata, ts_rank_cd(c.tsv, q.tsq) AS score
    FROM chunks AS c, q
    WHERE c.tenant_id = :tenant_id
      AND c.bot_id = :bot_id
      AND c.tsv @@ q.tsq
    ORDER BY score DESC, c.id
    LIMIT :limit
    """
)


# The metadata JSON stored with a chunk.
def _metadata(chunk: Chunk, source: Source) -> dict[str, Any]:
    # Display/citation facts only (no secrets, no internal config).
    return {
        "title": source.title or "",
        "section": chunk.section,
        "page": chunk.page,
        "url": chunk.url,
        "language": chunk.language,
        **chunk.extra,
    }


# Build a search hit from columns.
def _hit(
    chunk_id: UUID, source_id: UUID, content: str, meta: dict[str, Any], score: float
) -> ChunkHit:
    # Pull the citation facts back out of the metadata JSON.
    page = meta.get("page")
    # One hit.
    return ChunkHit(
        chunk_id=chunk_id,
        source_id=source_id,
        source_title=str(meta.get("title") or ""),
        text=content,
        section=str(meta.get("section") or ""),
        page=int(page) if isinstance(page, int) else None,
        url=meta.get("url") if isinstance(meta.get("url"), str) else None,
        score=float(score),
    )


# The repository.
class SqlAlchemyChunkRepository:
    """Implements ChunkRepository. The session must come from tenant_session() (RLS bound)."""

    # Keep the session.
    def __init__(self, session: AsyncSession) -> None:
        # The tenant-bound session.
        self._session = session

    # Delete a source's chunks and insert the new ones (caller's single transaction, R26).
    async def replace_for_source(
        self,
        source: Source,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        # One vector per chunk, or something upstream is broken.
        if len(chunks) != len(vectors):
            # Programming error, not user input.
            raise ValueError("chunks and vectors must have the same length")
        # 🔒 Remove the old chunks of this tenant's source.
        await self._session.execute(
            delete(ChunkRow).where(
                ChunkRow.tenant_id == source.tenant_id, ChunkRow.source_id == source.id
            )
        )
        # The new rows.
        rows = [
            {
                "id": uuid4(),
                "tenant_id": source.tenant_id,
                "bot_id": source.bot_id,
                "source_id": source.id,
                "chunk_index": chunk.index,
                "content": chunk.text,
                "embedding": list(vector),
                "metadata_": _metadata(chunk, source),
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        # Insert in batches (the tsv column is computed by Postgres itself).
        for start in range(0, len(rows), _INSERT_BATCH):
            # One multi-row INSERT.
            await self._session.execute(insert(ChunkRow), rows[start : start + _INSERT_BATCH])

    # How many chunks a source has.
    async def count_for_source(self, tenant_id: UUID, source_id: UUID) -> int:
        # 🔒 Tenant filter; served by uq_chunks_source_index.
        count = await self._session.scalar(
            select(func.count(ChunkRow.id)).where(
                ChunkRow.tenant_id == tenant_id, ChunkRow.source_id == source_id
            )
        )
        # 0 if none.
        return int(count or 0)

    # 'Same meaning' search.
    async def vector_search(
        self, tenant_id: UUID, bot_id: UUID, vector: Sequence[float], limit: int
    ) -> list[ChunkHit]:
        # Widen the HNSW candidate list for this transaction only (SET LOCAL resets at commit).
        await self._session.execute(text(f"SET LOCAL hnsw.ef_search = {_EF_SEARCH}"))
        # Cosine distance (0 = same direction).
        distance = ChunkRow.embedding.cosine_distance(list(vector))
        # serves: ix_chunks_embedding_hnsw (large bots) / ix_chunks_tenant_bot (small bots).
        rows = await self._session.execute(
            select(
                ChunkRow.id,
                ChunkRow.source_id,
                ChunkRow.content,
                ChunkRow.metadata_,
                (1 - distance).label("score"),
            )
            .where(ChunkRow.tenant_id == tenant_id, ChunkRow.bot_id == bot_id)
            .order_by(distance)
            .limit(limit)
        )
        # Score = cosine similarity.
        return [_hit(r.id, r.source_id, r.content, r.metadata_, r.score) for r in rows]

    # 'Same words' search.
    async def keyword_search(
        self, tenant_id: UUID, bot_id: UUID, query: str, limit: int
    ) -> list[ChunkHit]:
        # serves: ix_chunks_tsv (GIN) + ix_chunks_tenant_bot.
        rows = await self._session.execute(
            _KEYWORD_SQL,
            {"query": query, "tenant_id": tenant_id, "bot_id": bot_id, "limit": limit},
        )
        # Score = Postgres's cover-density rank.
        return [_hit(r.id, r.source_id, r.content, r.metadata or {}, r.score) for r in rows]
