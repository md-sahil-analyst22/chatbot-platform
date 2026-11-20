# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 Tenant A can never read or change tenant B's data, enforced by the database
#                itself.
# How to run: make test-db (needs a throwaway real Postgres - never Supabase; see
#             docs/runbooks/local-setup.md). Skipped otherwise.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Phase 1 exit criterion: tenant A cannot read or change tenant B's data (P1.6, R23, R37).

Runs on REAL Postgres as the non-owner app role (saathi_app, NOBYPASSRLS). The owner role
bypasses RLS and would make these tests meaningless, so it is used only to seed data.

Plan (from the original placeholder):
  1. As owner: insert tenant A, tenant B, and bot_b belonging to B.
  2. As saathi_app inside tenant_session(A): SELECT bot_b by id      -> no row.
  3. As saathi_app inside tenant_session(A): INSERT bot with tenant B -> RLS WITH CHECK error.
  4. As saathi_app with NO tenant set: SELECT * FROM bots             -> zero rows (fail closed).
  5. Through the API with a principal for A: GET/PATCH/DELETE bot_b   -> 404 (not 403).
Plus: the two SECURITY DEFINER lookups work for the app role and leak nothing else.
"""

# asyncio — runs many waiting tasks at once (async).
import asyncio

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From sqlalchemy — SQLAlchemy, our database toolkit: select = builds a SELECT query; text = a
#   raw SQL snippet.
from sqlalchemy import select, text

# From sqlalchemy.exc — database errors: DBAPIError = error raised by the database driver.
from sqlalchemy.exc import DBAPIError

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncEngine =
#   the async connection pool; AsyncSession = one unit of database work; async_sessionmaker =
#   factory that creates sessions.
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# From tests.db_fixtures — real-Postgres test helpers: requires_db = skips the test when no real
#   Postgres is available.
from tests.db_fixtures import requires_db

# From tests.fakes.builders — one-line builders for test objects: NOW = a fixed time for tests;
#   make_catalog = builds a test catalog; make_config = builds a test config.
from tests.fakes.builders import NOW, make_catalog, make_config

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: get_principal = verifies the login token.
from saathi.api.deps import get_principal

# From saathi.main — the FastAPI app factory: create_app = builds the FastAPI app.
from saathi.main import create_app

# From saathi.modules.tenancy.adapters.config_repository — database code for config versions:
#   SqlAlchemyBotConfigRepository = config versions in the database.
from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository

# From saathi.modules.tenancy.adapters.membership_lookup — login -> workspace lookup:
#   SqlAlchemyMembershipLookup = finds a user's workspace.
from saathi.modules.tenancy.adapters.membership_lookup import SqlAlchemyMembershipLookup

# From saathi.modules.tenancy.adapters.orm — the tenancy table classes: BotRow = bots table.
from saathi.modules.tenancy.adapters.orm import BotRow

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfigVersion = one saved version; ConfigStatus = draft/published/archived.
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion, ConfigStatus

# From saathi.platform.db.tenant_context — locks a database session to one tenant:
#   tenant_session = a session locked to one tenant.
from saathi.platform.db.tenant_context import tenant_session

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data.
from saathi.platform.errors import ConflictError

# From saathi.platform.security.auth — who is calling and what they may do: Membership = one
#   (workspace, role) pair; Principal = the verified caller; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Membership, Principal, Role

# Every test in this file is an integration test and needs the real database.
pytestmark = [pytest.mark.integration, requires_db]

# Two test tenants.
TENANT_A, TENANT_B = uuid4(), uuid4()
# One bot each.
BOT_A, BOT_B = uuid4(), uuid4()
# Tenant B's widget key.
KEY_B = "pk_" + "b" * 24


# A fixture: puts tenants A and B (with one bot each) into the database.
@pytest.fixture
# (needs the owner engine, which empties the tables first)
async def seeded(owner_engine: AsyncEngine) -> None:
    """Step 1, as the owner (bypasses RLS)."""
    # Connect as the owner (bypasses row-level security, to seed data).
    async with owner_engine.begin() as conn:
        # For each (tenant, bot, key):
        for tenant, bot, key in ((TENANT_A, BOT_A, "pk_" + "a" * 24), (TENANT_B, BOT_B, KEY_B)):
            # insert the tenant...
            await conn.execute(
                # (the SQL)
                text("INSERT INTO tenants (id, name) VALUES (:t, :n)"),
                # (its values)
                {"t": tenant, "n": f"tenant-{tenant}"},
            )
            # ...and its bot.
            await conn.execute(
                # (the SQL)
                text(
                    "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                    "VALUES (:b, :t, 'Mitra', ARRAY['en'], :k)"
                ),
                # (its values)
                {"b": bot, "t": tenant, "k": key},
            )
        # Also a login 'user-b' who owns tenant B.
        await conn.execute(
            # (the SQL)
            text(
                "INSERT INTO user_accounts (tenant_id, auth_user_id, email, role) "
                "VALUES (:t, 'user-b', 'b@example.com', 'owner')"
            ),
            # (its values)
            {"t": TENANT_B},
        )


# Helper: the ids of every bot this session can see.
async def _bot_ids(session: AsyncSession) -> set[UUID]:
    # SELECT bots.id, as a set.
    return set(await session.scalars(select(BotRow.id)))


# 🔒 Locked to tenant A, you see only A's bots.
async def test_tenant_a_cannot_read_tenant_b(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Step 2 - even WITHOUT a tenant filter in the query, RLS hides B's rows.
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        # Only A's bot is visible.
        assert await _bot_ids(session) == {BOT_A}
        # B's bot can't even be fetched by id.
        assert await session.get(BotRow, BOT_B) is None


# 🔒 Tenant A can't insert rows for tenant B.
async def test_tenant_a_cannot_write_rows_for_tenant_b(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Step 3 - WITH CHECK refuses a row labelled with another tenant.
    with pytest.raises(DBAPIError, match="row-level security"):
        # Locked to tenant A...
        async with tenant_session(app_sessionmaker, TENANT_A) as session:
            # ...try to insert a bot that says it belongs to B.
            await session.execute(
                # (the SQL)
                text(
                    "INSERT INTO bots (tenant_id, name, languages, public_key) "
                    "VALUES (:t, 'Sneaky', ARRAY['en'], 'pk_cccccccccccccccccccccccc')"
                ),
                # (its values)
                {"t": TENANT_B},
            )


# 🔒 Tenant A can't change or delete tenant B's rows.
async def test_tenant_a_cannot_update_or_delete_tenant_b_rows(
    # (needs the seeded data,
    seeded: None,
    # saathi_app sessions,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    # and the owner engine to check afterwards)
    owner_engine: AsyncEngine,
) -> None:
    # Locked to tenant A:
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        # try to rename B's bot,
        updated = await session.execute(
            text("UPDATE bots SET name = 'hijacked' WHERE id = :b"), {"b": BOT_B}
        )
        # and try to delete it.
        deleted = await session.execute(text("DELETE FROM bots WHERE id = :b"), {"b": BOT_B})
        # Neither touched a single row.
        assert updated.rowcount == 0 and deleted.rowcount == 0  # type: ignore[attr-defined]
    # Check as the owner...
    async with owner_engine.connect() as conn:
        # ...that B's bot still has its original name.
        assert (
            await conn.scalar(text("SELECT name FROM bots WHERE id = :b"), {"b": BOT_B}) == "Mitra"
        )


# 🔒 With no tenant set, nothing is visible (fail closed).
async def test_no_tenant_set_sees_nothing(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Step 4 - fail closed, including on a pooled connection that had a tenant before.
    async with app_sessionmaker() as session:
        # No bots visible.
        assert await _bot_ids(session) == set()
        # No tenants visible either.
        assert await session.scalar(text("SELECT count(*) FROM tenants")) == 0
    # Locked to tenant A...
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        # ...A's bot is visible.
        assert await _bot_ids(session) == {BOT_A}
    # A new session without a tenant...
    async with app_sessionmaker() as session:
        assert await _bot_ids(session) == set()  # tenant was transaction-scoped


# 🔒 A row can't point at another tenant's parent (e.g. a config for B's bot).
async def test_tenant_cannot_link_to_another_tenants_parent(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Composite (tenant_id, bot_id) foreign key: FK checks ignore RLS, the composite key doesn't.
    with pytest.raises(DBAPIError, match="foreign key"):
        # Locked to tenant A...
        async with tenant_session(app_sessionmaker, TENANT_A) as session:
            # ...try to save a config version for tenant B's bot.
            await session.execute(
                # (the SQL)
                text(
                    "INSERT INTO bot_config_versions (tenant_id, bot_id, version, status, "
                    "config, created_by) VALUES (:t, :b, 1, 'draft', '{}', 'x')"
                ),
                # (its values)
                {"t": TENANT_A, "b": BOT_B},
            )


# A fixture: the real app on real Postgres, logged in as tenant A's owner.
@pytest.fixture
# It gives each test an HTTP client.
async def api_as_tenant_a(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> AsyncIterator[httpx.AsyncClient]:
    # The real app.
    app = create_app()
    # Run start-up.
    async with app.router.lifespan_context(app):
        app.state.sessionmaker = app_sessionmaker  # real Postgres, as saathi_app
        app.state.model_catalog = make_catalog()  # "standard" on every plan, "advanced" on pro
        # Skip login: the caller is always tenant A's owner.
        app.dependency_overrides[get_principal] = lambda: Principal(
            user_id="user-a", tenant_id=TENANT_A, role=Role.OWNER
        )
        # Send requests straight into the app.
        transport = httpx.ASGITransport(app=app)
        # A client.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Lend it to the test.
            yield client


# 🔒 Through the API, tenant B's bot looks like it doesn't exist.
async def test_api_returns_404_for_another_tenants_bot(
    api_as_tenant_a: httpx.AsyncClient, owner_engine: AsyncEngine
) -> None:
    # Step 5 - 404, not 403: don't even confirm the bot exists.
    client = api_as_tenant_a
    # A's own bot: 200.
    assert (await client.get(f"/api/v1/bots/{BOT_A}")).status_code == 200
    # B's bot: 404.
    assert (await client.get(f"/api/v1/bots/{BOT_B}")).status_code == 404
    # Changing B's bot: 404.
    assert (await client.patch(f"/api/v1/bots/{BOT_B}", json={"name": "x"})).status_code == 404
    # Deleting B's bot: 404.
    assert (await client.delete(f"/api/v1/bots/{BOT_B}")).status_code == 404
    # B's bot's versions: empty list.
    assert (await client.get(f"/api/v1/bots/{BOT_B}/config/versions")).json() == []
    # The bot list contains only A's bot.
    assert [b["id"] for b in (await client.get("/api/v1/bots")).json()] == [str(BOT_A)]
    # Check as the owner...
    async with owner_engine.connect() as conn:
        # ...that B's bot still exists.
        assert await conn.scalar(text("SELECT count(*) FROM bots WHERE id = :b"), {"b": BOT_B}) == 1


# The whole bot + config flow works end to end on real Postgres.
async def test_api_crud_and_config_flow_on_real_postgres(
    # (uses the API fixture)
    api_as_tenant_a: httpx.AsyncClient,
) -> None:
    """P1.8 end to end through SQL repositories + RLS (no fakes)."""
    # The client.
    client = api_as_tenant_a
    # Create a bot.
    r = await client.post("/api/v1/bots", json={"name": "Sahayak", "languages": ["hi", "en"]})
    # 201.
    assert r.status_code == 201
    # Its id.
    bot_id = r.json()["id"]
    # Creating another with the same name...
    assert (
        await client.post("/api/v1/bots", json={"name": "Sahayak", "languages": ["en"]})
    ).status_code == 409
    # Change the persona to Hindi text...
    assert (await client.patch(f"/api/v1/bots/{bot_id}", json={"persona": "विनम्र"})).json()[
        "persona"
    ] == "विनम्र"

    # The config address.
    base = f"/api/v1/bots/{bot_id}/config"
    # Config 1.
    v1 = {"branding": {"header_title": "Sahayak v1"}, "generation": {"model_key": "standard"}}
    # Config 2.
    v2 = {"branding": {"header_title": "Sahayak v2"}, "generation": {"model_key": "standard"}}
    # A config using the pro-only model.
    pro_only = {"branding": {"header_title": "x"}, "generation": {"model_key": "advanced"}}
    assert (await client.post(f"{base}/versions", json=pro_only)).status_code == 422  # starter
    # Save config 1 -> version 1.
    assert (await client.post(f"{base}/versions", json=v1)).json()["version"] == 1
    # Publish it.
    assert (await client.post(f"{base}/versions/1/publish")).json()["status"] == "published"
    # Save config 2 -> version 2.
    assert (await client.post(f"{base}/versions", json=v2)).json()["version"] == 2
    # Publish it.
    assert (await client.post(f"{base}/versions/2/publish")).status_code == 200
    # Read the live version.
    published = (await client.get(f"{base}/published")).json()
    # It's config 2.
    assert published["config"]["branding"]["header_title"] == "Sahayak v2"
    # Rollback re-publishes v1 as a NEW version; history stays intact (R22).
    rolled = (await client.post(f"{base}/versions/1/rollback")).json()
    # That made version 3, now live.
    assert (rolled["version"], rolled["status"]) == (3, "published")
    # All versions' statuses.
    statuses = {v["version"]: v["status"] for v in (await client.get(f"{base}/versions")).json()}
    # 3 live, 2 and 1 archived.
    assert statuses == {3: "published", 2: "archived", 1: "archived"}

    # Delete the bot: 204.
    assert (await client.delete(f"/api/v1/bots/{bot_id}")).status_code == 204
    # It's gone: 404.
    assert (await client.get(f"/api/v1/bots/{bot_id}")).status_code == 404


# 🔒 The login lookup works for saathi_app and reveals nothing more.
async def test_membership_lookup_works_for_app_role_and_leaks_nothing_else(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # The real membership lookup.
    lookup = SqlAlchemyMembershipLookup(app_sessionmaker)
    # user-b is the owner of tenant B.
    assert await lookup.memberships("user-b") == [Membership(TENANT_B, Role.OWNER)]
    # An unknown user has no memberships.
    assert await lookup.memberships("nobody") == []
    async with app_sessionmaker() as session:  # the table itself stays invisible without a tenant
        # No rows visible.
        assert await session.scalar(text("SELECT count(*) FROM user_accounts")) == 0


# 🔒 The widget-key lookup returns two ids and nothing else.
async def test_widget_key_lookup_returns_only_ids(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # A session with no tenant set.
    async with app_sessionmaker() as session:
        # Call the lookup function with B's key...
        rows = (
            await session.execute(text("SELECT * FROM resolve_bot_public_key(:k)"), {"k": KEY_B})
        ).all()
        # Exactly one row: (tenant B, bot B).
        assert [tuple(r) for r in rows] == [(TENANT_B, BOT_B)]
        # And only those two columns.
        assert list(rows[0]._mapping) == ["tenant_id", "bot_id"]


# 🔒 Two publishes at the same moment: one wins, the other gets 409.
async def test_concurrent_publish_leaves_exactly_one_published_version(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Two publishes racing in separate transactions: one wins, the other gets ConflictError."""
    # Locked to tenant A:
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        # the real config repository,
        repo = SqlAlchemyBotConfigRepository(session)
        # two drafts (versions 1 and 2),
        drafts = [_version(TENANT_A, BOT_A, n) for n in (1, 2)]
        # save each...
        for draft in drafts:
            # ...one by one.
            await repo.add(draft)

    # A signal the first publish raises once it has written.
    started = asyncio.Event()

    # One publish attempt; `wait` says whether to hold the transaction open.
    async def publish(draft: BotConfigVersion, wait: bool) -> str:
        # Try:
        try:
            # in its own transaction locked to tenant A,
            async with tenant_session(app_sessionmaker, TENANT_A) as session:
                # mark this draft published,
                await SqlAlchemyBotConfigRepository(session).update_status(draft.published())
                # signal that the write happened,
                started.set()
                # and the first attempt...
                if not wait:
                    await asyncio.sleep(0.2)  # hold the transaction open while the other runs
            # Committed: it won.
            return "published"
        # The database refused it (another publish already holds 'published'):
        except ConflictError:
            # it lost.
            return "conflict"

    # Start the first publish in the background.
    first = asyncio.create_task(publish(drafts[0], wait=False))
    # Wait until it has written.
    await started.wait()
    # Now run the second publish while the first is still open.
    second = await publish(drafts[1], wait=True)
    # One won, one got a conflict.
    assert sorted([await first, second]) == ["conflict", "published"]

    # Locked to tenant A again:
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        # read the live version.
        live = await SqlAlchemyBotConfigRepository(session).published(TENANT_A, BOT_A)
        # Exactly version 1 is live.
        assert live is not None and live.version == 1


# Helper: a draft config version for (tenant, bot, number).
def _version(tenant: UUID, bot: UUID, n: int) -> BotConfigVersion:
    # Build it.
    return BotConfigVersion(uuid4(), tenant, bot, n, ConfigStatus.DRAFT, make_config(), "u", NOW)
