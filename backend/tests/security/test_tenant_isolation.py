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

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.db_fixtures import requires_db
from tests.fakes.builders import NOW, make_catalog, make_config

from saathi.api.deps import get_principal
from saathi.main import create_app
from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository
from saathi.modules.tenancy.adapters.membership_lookup import SqlAlchemyMembershipLookup
from saathi.modules.tenancy.adapters.orm import BotRow
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion, ConfigStatus
from saathi.platform.db.tenant_context import tenant_session
from saathi.platform.errors import ConflictError
from saathi.platform.security.auth import Membership, Principal, Role

pytestmark = [pytest.mark.integration, requires_db]

TENANT_A, TENANT_B = uuid4(), uuid4()
BOT_A, BOT_B = uuid4(), uuid4()
KEY_B = "pk_" + "b" * 24


@pytest.fixture
async def seeded(owner_engine: AsyncEngine) -> None:
    """Step 1, as the owner (bypasses RLS)."""
    async with owner_engine.begin() as conn:
        for tenant, bot, key in ((TENANT_A, BOT_A, "pk_" + "a" * 24), (TENANT_B, BOT_B, KEY_B)):
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:t, :n)"),
                {"t": tenant, "n": f"tenant-{tenant}"},
            )
            await conn.execute(
                text(
                    "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                    "VALUES (:b, :t, 'Mitra', ARRAY['en'], :k)"
                ),
                {"b": bot, "t": tenant, "k": key},
            )
        await conn.execute(
            text(
                "INSERT INTO user_accounts (tenant_id, auth_user_id, email, role) "
                "VALUES (:t, 'user-b', 'b@example.com', 'owner')"
            ),
            {"t": TENANT_B},
        )


async def _bot_ids(session: AsyncSession) -> set[UUID]:
    return set(await session.scalars(select(BotRow.id)))


async def test_tenant_a_cannot_read_tenant_b(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Step 2 - even WITHOUT a tenant filter in the query, RLS hides B's rows.
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        assert await _bot_ids(session) == {BOT_A}
        assert await session.get(BotRow, BOT_B) is None


async def test_tenant_a_cannot_write_rows_for_tenant_b(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Step 3 - WITH CHECK refuses a row labelled with another tenant.
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_session(app_sessionmaker, TENANT_A) as session:
            await session.execute(
                text(
                    "INSERT INTO bots (tenant_id, name, languages, public_key) "
                    "VALUES (:t, 'Sneaky', ARRAY['en'], 'pk_cccccccccccccccccccccccc')"
                ),
                {"t": TENANT_B},
            )


async def test_tenant_a_cannot_update_or_delete_tenant_b_rows(
    seeded: None,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    owner_engine: AsyncEngine,
) -> None:
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        updated = await session.execute(
            text("UPDATE bots SET name = 'hijacked' WHERE id = :b"), {"b": BOT_B}
        )
        deleted = await session.execute(text("DELETE FROM bots WHERE id = :b"), {"b": BOT_B})
        assert updated.rowcount == 0 and deleted.rowcount == 0  # type: ignore[attr-defined]
    async with owner_engine.connect() as conn:
        assert (
            await conn.scalar(text("SELECT name FROM bots WHERE id = :b"), {"b": BOT_B}) == "Mitra"
        )


async def test_no_tenant_set_sees_nothing(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Step 4 - fail closed, including on a pooled connection that had a tenant before.
    async with app_sessionmaker() as session:
        assert await _bot_ids(session) == set()
        assert await session.scalar(text("SELECT count(*) FROM tenants")) == 0
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        assert await _bot_ids(session) == {BOT_A}
    async with app_sessionmaker() as session:
        assert await _bot_ids(session) == set()  # tenant was transaction-scoped


async def test_tenant_cannot_link_to_another_tenants_parent(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # Composite (tenant_id, bot_id) foreign key: FK checks ignore RLS, the composite key doesn't.
    with pytest.raises(DBAPIError, match="foreign key"):
        async with tenant_session(app_sessionmaker, TENANT_A) as session:
            await session.execute(
                text(
                    "INSERT INTO bot_config_versions (tenant_id, bot_id, version, status, "
                    "config, created_by) VALUES (:t, :b, 1, 'draft', '{}', 'x')"
                ),
                {"t": TENANT_A, "b": BOT_B},
            )


@pytest.fixture
async def api_as_tenant_a(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.sessionmaker = app_sessionmaker  # real Postgres, as saathi_app
        app.state.model_catalog = make_catalog()  # "standard" on every plan, "advanced" on pro
        app.dependency_overrides[get_principal] = lambda: Principal(
            user_id="user-a", tenant_id=TENANT_A, role=Role.OWNER
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_api_returns_404_for_another_tenants_bot(
    api_as_tenant_a: httpx.AsyncClient, owner_engine: AsyncEngine
) -> None:
    # Step 5 - 404, not 403: don't even confirm the bot exists.
    client = api_as_tenant_a
    assert (await client.get(f"/api/v1/bots/{BOT_A}")).status_code == 200
    assert (await client.get(f"/api/v1/bots/{BOT_B}")).status_code == 404
    assert (await client.patch(f"/api/v1/bots/{BOT_B}", json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/api/v1/bots/{BOT_B}")).status_code == 404
    assert (await client.get(f"/api/v1/bots/{BOT_B}/config/versions")).json() == []
    assert [b["id"] for b in (await client.get("/api/v1/bots")).json()] == [str(BOT_A)]
    async with owner_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM bots WHERE id = :b"), {"b": BOT_B}) == 1


async def test_api_crud_and_config_flow_on_real_postgres(
    api_as_tenant_a: httpx.AsyncClient,
) -> None:
    """P1.8 end to end through SQL repositories + RLS (no fakes)."""
    client = api_as_tenant_a
    r = await client.post("/api/v1/bots", json={"name": "Sahayak", "languages": ["hi", "en"]})
    assert r.status_code == 201
    bot_id = r.json()["id"]
    assert (
        await client.post("/api/v1/bots", json={"name": "Sahayak", "languages": ["en"]})
    ).status_code == 409
    assert (await client.patch(f"/api/v1/bots/{bot_id}", json={"persona": "विनम्र"})).json()[
        "persona"
    ] == "विनम्र"

    base = f"/api/v1/bots/{bot_id}/config"
    v1 = {"branding": {"header_title": "Sahayak v1"}, "generation": {"model_key": "standard"}}
    v2 = {"branding": {"header_title": "Sahayak v2"}, "generation": {"model_key": "standard"}}
    pro_only = {"branding": {"header_title": "x"}, "generation": {"model_key": "advanced"}}
    assert (await client.post(f"{base}/versions", json=pro_only)).status_code == 422  # starter
    assert (await client.post(f"{base}/versions", json=v1)).json()["version"] == 1
    assert (await client.post(f"{base}/versions/1/publish")).json()["status"] == "published"
    assert (await client.post(f"{base}/versions", json=v2)).json()["version"] == 2
    assert (await client.post(f"{base}/versions/2/publish")).status_code == 200
    published = (await client.get(f"{base}/published")).json()
    assert published["config"]["branding"]["header_title"] == "Sahayak v2"
    # Rollback re-publishes v1 as a NEW version; history stays intact (R22).
    rolled = (await client.post(f"{base}/versions/1/rollback")).json()
    assert (rolled["version"], rolled["status"]) == (3, "published")
    statuses = {v["version"]: v["status"] for v in (await client.get(f"{base}/versions")).json()}
    assert statuses == {3: "published", 2: "archived", 1: "archived"}

    assert (await client.delete(f"/api/v1/bots/{bot_id}")).status_code == 204
    assert (await client.get(f"/api/v1/bots/{bot_id}")).status_code == 404


async def test_membership_lookup_works_for_app_role_and_leaks_nothing_else(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    lookup = SqlAlchemyMembershipLookup(app_sessionmaker)
    assert await lookup.memberships("user-b") == [Membership(TENANT_B, Role.OWNER)]
    assert await lookup.memberships("nobody") == []
    async with app_sessionmaker() as session:  # the table itself stays invisible without a tenant
        assert await session.scalar(text("SELECT count(*) FROM user_accounts")) == 0


async def test_widget_key_lookup_returns_only_ids(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with app_sessionmaker() as session:
        rows = (
            await session.execute(text("SELECT * FROM resolve_bot_public_key(:k)"), {"k": KEY_B})
        ).all()
        assert [tuple(r) for r in rows] == [(TENANT_B, BOT_B)]
        assert list(rows[0]._mapping) == ["tenant_id", "bot_id"]


async def test_concurrent_publish_leaves_exactly_one_published_version(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Two publishes racing in separate transactions: one wins, the other gets ConflictError."""
    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        repo = SqlAlchemyBotConfigRepository(session)
        drafts = [_version(TENANT_A, BOT_A, n) for n in (1, 2)]
        for draft in drafts:
            await repo.add(draft)

    started = asyncio.Event()

    async def publish(draft: BotConfigVersion, wait: bool) -> str:
        try:
            async with tenant_session(app_sessionmaker, TENANT_A) as session:
                await SqlAlchemyBotConfigRepository(session).update_status(draft.published())
                started.set()
                if not wait:
                    await asyncio.sleep(0.2)  # hold the transaction open while the other runs
            return "published"
        except ConflictError:
            return "conflict"

    first = asyncio.create_task(publish(drafts[0], wait=False))
    await started.wait()
    second = await publish(drafts[1], wait=True)
    assert sorted([await first, second]) == ["conflict", "published"]

    async with tenant_session(app_sessionmaker, TENANT_A) as session:
        live = await SqlAlchemyBotConfigRepository(session).published(TENANT_A, BOT_A)
        assert live is not None and live.version == 1


def _version(tenant: UUID, bot: UUID, n: int) -> BotConfigVersion:
    return BotConfigVersion(uuid4(), tenant, bot, n, ConfigStatus.DRAFT, make_config(), "u", NOW)
