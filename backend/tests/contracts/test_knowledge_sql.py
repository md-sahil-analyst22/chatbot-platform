# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The SQL knowledge repositories run the SAME contract classes as the fakes
#                (R35), on a real, throwaway Postgres (never Supabase). They run as the schema
#                owner, so they prove the repositories' own tenant filters (R15); RLS for the app
#                role is proven in tests/security/test_knowledge_isolation.py.
# How to run: make test-db (needs TEST_DATABASE_URL + TEST_APP_DATABASE_URL, see
#             docs/runbooks/local-setup.md). Skipped otherwise.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQL knowledge repositories vs. their contracts."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# pytest — the test framework.
import pytest

# From sqlalchemy — text = a raw SQL snippet (to insert parent rows).
from sqlalchemy import text

# From tests.contracts.test_knowledge_repository_contract — the shared contract classes.
from tests.contracts.test_knowledge_repository_contract import (
    ChunkRepositoryContract,
    FaqRepositoryContract,
    SourceRepositoryContract,
)

# From tests.contracts.test_sql_repositories — _OwnerSession = one transaction per test, always
#   rolled back.
from tests.contracts.test_sql_repositories import _OwnerSession

# From tests.db_fixtures — requires_db = skip unless a real Postgres is configured.
from tests.db_fixtures import requires_db

# From saathi.modules.knowledge.adapters.chunk_repository — SqlAlchemyChunkRepository.
from saathi.modules.knowledge.adapters.chunk_repository import SqlAlchemyChunkRepository

# From saathi.modules.knowledge.adapters.faq_repository — SqlAlchemyFaqRepository.
from saathi.modules.knowledge.adapters.faq_repository import SqlAlchemyFaqRepository

# From saathi.modules.knowledge.adapters.source_repository — SqlAlchemySourceRepository.
from saathi.modules.knowledge.adapters.source_repository import SqlAlchemySourceRepository

# From saathi.modules.knowledge.ports.repositories — the contract types.
from saathi.modules.knowledge.ports.repositories import (
    ChunkRepository,
    FaqRepository,
    SourceRepository,
)

# Every test here needs real Postgres.
pytestmark = [pytest.mark.integration, requires_db]


# Creates the parent tenant/bot rows the composite foreign keys need.
class _SqlSeeds(_OwnerSession):
    # Make the (tenant, bot) pair exist in the database.
    async def seed_bot(self, tenant_id: UUID, bot_id: UUID) -> None:
        # The tenant (once).
        await self.session.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, 'k') ON CONFLICT DO NOTHING"),
            {"id": tenant_id},
        )
        # The bot (once), with a unique public key.
        await self.session.execute(
            text(
                "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                "VALUES (:id, :t, :n, ARRAY['en'], :pk) ON CONFLICT DO NOTHING"
            ),
            {"id": bot_id, "t": tenant_id, "n": str(bot_id), "pk": f"pk_{uuid4().hex}"},
        )


# The source contract on Postgres.
class TestSqlSourceRepository(_SqlSeeds, SourceRepositoryContract):
    # The SQL adapter on the test's session.
    def make(self) -> SourceRepository:
        # Build it.
        return SqlAlchemySourceRepository(self.session)


# The chunk contract on Postgres (vector + full-text search for real).
class TestSqlChunkRepository(_SqlSeeds, ChunkRepositoryContract):
    # Chunk and source adapters on the same session.
    def make(self) -> tuple[ChunkRepository, SourceRepository]:
        # Build both.
        return SqlAlchemyChunkRepository(self.session), SqlAlchemySourceRepository(self.session)


# The FAQ contract on Postgres.
class TestSqlFaqRepository(_SqlSeeds, FaqRepositoryContract):
    # The SQL adapter on the test's session.
    def make(self) -> FaqRepository:
        # Build it.
        return SqlAlchemyFaqRepository(self.session)
