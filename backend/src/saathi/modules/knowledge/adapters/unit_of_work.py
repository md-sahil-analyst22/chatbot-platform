# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Opens one short, tenant-bound database transaction and hands out the knowledge
#       repositories inside it (implements IngestionUnitOfWork). Used by the background job.
# The chunking-settings reader comes from tenancy, which this module may not import (R4), so
#   bootstrap/ passes in a small factory that builds it from the same session.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQL unit of work for ingestion."""

# From collections.abc — standard type names: AsyncIterator = async generator type; Callable =
#   a function type.
from collections.abc import AsyncIterator, Callable

# From contextlib — context-manager helpers: asynccontextmanager = turns a generator into an
#   `async with` block.
from contextlib import asynccontextmanager

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From sqlalchemy.ext.asyncio — async database sessions: AsyncSession = one session;
#   async_sessionmaker = makes sessions.
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# From saathi.modules.knowledge.adapters.chunk_repository — SQL chunks: SqlAlchemyChunkRepository.
from saathi.modules.knowledge.adapters.chunk_repository import SqlAlchemyChunkRepository

# From saathi.modules.knowledge.adapters.source_repository — SQL sources:
#   SqlAlchemySourceRepository.
from saathi.modules.knowledge.adapters.source_repository import SqlAlchemySourceRepository

# From saathi.modules.knowledge.ports.external — outside needs: ChunkingPolicySource = which
#   chunking settings a bot uses.
from saathi.modules.knowledge.ports.external import ChunkingPolicySource

# From saathi.modules.knowledge.ports.unit_of_work — transactions: IngestionRepositories = the
#   repositories inside one transaction.
from saathi.modules.knowledge.ports.unit_of_work import IngestionRepositories

# From saathi.platform.db.tenant_context — tenant-bound sessions: tenant_session = session +
#   transaction with RLS bound to one tenant.
from saathi.platform.db.tenant_context import tenant_session

# Builds a chunking-settings reader on a given session (supplied by bootstrap/).
PolicySourceFactory = Callable[[AsyncSession], ChunkingPolicySource]


# The unit of work.
class SqlIngestionUnitOfWork:
    """Callable: `async with uow(tenant_id) as repos:` = one committed transaction."""

    # Keep the session maker and the policy-reader factory.
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        policy_source_factory: PolicySourceFactory,
    ) -> None:
        # Makes sessions (one per transaction).
        self._sessionmaker = sessionmaker
        # Builds the chunking-settings reader.
        self._policy_source_factory = policy_source_factory

    # Open the transaction for one tenant.
    @asynccontextmanager
    async def __call__(self, tenant_id: UUID) -> AsyncIterator[IngestionRepositories]:
        # Session + transaction with the tenant bound (RLS); commits at the end of the block.
        async with tenant_session(self._sessionmaker, tenant_id) as session:
            # Hand out repositories that all share this session.
            yield IngestionRepositories(
                sources=SqlAlchemySourceRepository(session),
                chunks=SqlAlchemyChunkRepository(session),
                policies=self._policy_source_factory(session),
            )
