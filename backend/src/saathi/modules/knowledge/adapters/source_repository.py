# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Saves and loads sources in Postgres (implements SourceRepository).
# 🔒 Every query filters by tenant_id (R15) on top of row-level security; the session must come
#    from tenant_session() so RLS is bound to the same tenant.
# Locking: get_for_update / all_for_bot_for_update use SELECT ... FOR UPDATE so two workers (or a
#    worker and a publish) can't change the same source at the same time.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQL source repository."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From sqlalchemy — SQLAlchemy, our database toolkit: Select = the type of a SELECT statement;
#   delete = DELETE statement; func = SQL functions (count, now); select = SELECT statement;
#   update = UPDATE statement.
from sqlalchemy import Select, delete, func, select, update

# From sqlalchemy.exc — database errors: IntegrityError = a constraint was violated.
from sqlalchemy.exc import IntegrityError

# From sqlalchemy.ext.asyncio — async database sessions: AsyncSession = one async session.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.modules.knowledge.adapters.orm — knowledge tables: ChunkRow = chunks table;
#   SourceRow = sources table.
from saathi.modules.knowledge.adapters.orm import ChunkRow, SourceRow

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions = one crawl's settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — sources: Source = one document/site;
#   SourceStatus = its life-cycle states.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.modules.knowledge.ports.repositories — storage contracts: SourceListing = source +
#   bookkeeping.
from saathi.modules.knowledge.ports.repositories import SourceListing

# From saathi.platform.db.errors — database error helper: violated_constraint = which rule fired.
from saathi.platform.db.errors import violated_constraint

# From saathi.platform.errors — our error types: ConflictError = 409; NotFoundError = 404.
from saathi.platform.errors import ConflictError, NotFoundError

# The 'same file/URL twice for one bot' rule.
_DUPLICATE_URI = "uq_sources_tenant_bot_uri"
# The rule that the bot exists for this tenant (composite foreign key).
_BOT_FK = "fk_sources_tenant_id_bots"


# Turn a database row into a domain Source.
def _to_domain(row: SourceRow) -> Source:
    # Copy the fields; crawl settings are rebuilt (and re-validated) from JSON.
    return Source(
        id=row.id,
        tenant_id=row.tenant_id,
        bot_id=row.bot_id,
        kind=row.kind,
        uri=row.uri,
        content_hash=row.content_hash,
        status=SourceStatus(row.status),
        title=row.title,
        error=row.error,
        crawl=CrawlOptions.from_json(row.options) if row.options else None,
    )


# The repository.
class SqlAlchemySourceRepository:
    """Implements SourceRepository. The session must come from tenant_session() (RLS bound)."""

    # Keep the session.
    def __init__(self, session: AsyncSession) -> None:
        # The tenant-bound session.
        self._session = session

    # Save a new source.
    async def add(self, source: Source) -> None:
        # Stage the row.
        self._session.add(
            SourceRow(
                id=source.id,
                tenant_id=source.tenant_id,
                bot_id=source.bot_id,
                kind=source.kind,
                uri=source.uri,
                title=source.title,
                status=source.status.value,
                content_hash=source.content_hash,
                error=source.error,
                options=source.crawl.to_json() if source.crawl else None,
            )
        )
        # Send it now so constraint errors surface here.
        try:
            # Flush = run the INSERT inside the current transaction.
            await self._session.flush()
        # A rule was broken.
        except IntegrityError as exc:
            # Which one?
            name = violated_constraint(exc)
            # Same file/URL already added (concurrently).
            if name == _DUPLICATE_URI:
                # 409.
                raise ConflictError("this source already exists for the bot") from exc
            # The bot doesn't exist for this tenant.
            if name == _BOT_FK:
                # 404 (never reveal another tenant's bot).
                raise NotFoundError("bot not found") from exc
            # Anything else is a bug: re-raise unchanged.
            raise

    # Shared SELECT for one source of one tenant.
    def _select_one(self, tenant_id: UUID, source_id: UUID) -> Select[SourceRow]:
        # 🔒 Filter by tenant AND id.
        return select(SourceRow).where(SourceRow.id == source_id, SourceRow.tenant_id == tenant_id)

    # Load one source.
    async def get(self, tenant_id: UUID, source_id: UUID) -> Source | None:
        # Run the query.
        row = await self._session.scalar(self._select_one(tenant_id, source_id))
        # Convert, or None.
        return _to_domain(row) if row is not None else None

    # Load a bot's source by location.
    async def get_by_uri(self, tenant_id: UUID, bot_id: UUID, uri: str) -> Source | None:
        # Served by the uq_sources_tenant_bot_uri unique index.
        row = await self._session.scalar(
            select(SourceRow).where(
                SourceRow.tenant_id == tenant_id,
                SourceRow.bot_id == bot_id,
                SourceRow.uri == uri,
            )
        )
        # Convert, or None.
        return _to_domain(row) if row is not None else None

    # Load one source and lock its row until the transaction ends.
    async def get_for_update(self, tenant_id: UUID, source_id: UUID) -> Source | None:
        # SELECT ... FOR UPDATE: a second job waits here until the first commits.
        row = await self._session.scalar(self._select_one(tenant_id, source_id).with_for_update())
        # Convert, or None.
        return _to_domain(row) if row is not None else None

    # Save status, fingerprint, error and title.
    async def save(self, source: Source) -> None:
        # The columns to write.
        values: dict[str, object] = {
            "status": source.status.value,
            "content_hash": source.content_hash,
            "error": source.error,
            "title": source.title,
            "options": source.crawl.to_json() if source.crawl else None,
        }
        # A finished run records when it finished.
        if source.status is SourceStatus.READY:
            # Database clock (one clock for all API/worker replicas).
            values["synced_at"] = func.now()
        # 🔒 UPDATE only this tenant's row.
        result = await self._session.execute(
            update(SourceRow)
            .where(SourceRow.id == source.id, SourceRow.tenant_id == source.tenant_id)
            .values(**values)
        )
        # Nothing updated: it was deleted.
        if result.rowcount == 0:  # type: ignore[attr-defined]  # CursorResult for UPDATE
            # 404.
            raise NotFoundError("source not found")

    # Delete one source (its chunks go with it: foreign key ON DELETE CASCADE).
    async def delete(self, tenant_id: UUID, source_id: UUID) -> bool:
        # 🔒 DELETE only this tenant's row.
        result = await self._session.execute(
            delete(SourceRow).where(SourceRow.id == source_id, SourceRow.tenant_id == tenant_id)
        )
        # True if a row went away.
        return bool(result.rowcount)  # type: ignore[attr-defined]  # CursorResult for DELETE

    # A bot's sources with chunk counts, newest first.
    async def list_for_bot(self, tenant_id: UUID, bot_id: UUID, limit: int) -> list[SourceListing]:
        # Chunk count per source, as a correlated subquery (served by uq_chunks_source_index).
        chunk_count = (
            select(func.count(ChunkRow.id))
            .where(ChunkRow.source_id == SourceRow.id, ChunkRow.tenant_id == tenant_id)
            .scalar_subquery()
        )
        # serves: ix_sources_tenant_bot_created (tenant, bot, newest first).
        rows = await self._session.execute(
            select(SourceRow, chunk_count)
            .where(SourceRow.tenant_id == tenant_id, SourceRow.bot_id == bot_id)
            .order_by(SourceRow.created_at.desc())
            .limit(limit)
        )
        # One listing per row.
        return [
            SourceListing(
                source=_to_domain(row),
                created_at=row.created_at,
                synced_at=row.synced_at,
                chunk_count=int(count or 0),
            )
            for row, count in rows.all()
        ]

    # Every source of a bot, locked.
    async def all_for_bot_for_update(self, tenant_id: UUID, bot_id: UUID) -> list[Source]:
        # 🔒 Tenant + bot filter; locked in a stable order (avoids deadlocks between two callers).
        rows = await self._session.scalars(
            select(SourceRow)
            .where(SourceRow.tenant_id == tenant_id, SourceRow.bot_id == bot_id)
            .order_by(SourceRow.id)
            .with_for_update()
        )
        # Convert each.
        return [_to_domain(r) for r in rows]
