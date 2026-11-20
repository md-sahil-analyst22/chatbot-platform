# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 The public widget lookup on real Postgres: only safe fields, unknown keys ->
#                404.
# How to run: make test-db (needs a throwaway real Postgres - never Supabase; see
#             docs/runbooks/local-setup.md). Skipped otherwise.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""P1.11 public widget lookup, end to end on REAL Postgres as saathi_app (R10, R23, R37).

GET /public/v1/widgets/{public_key}/config has no login: the public key is resolved by the narrow
SECURITY DEFINER function resolve_bot_public_key(), then the published config is read inside that
tenant's RLS scope. These tests prove the whole path (function + RLS + SQL repositories + route):
the right tenant's look only, published versions only, public fields only, and no way to tell an
unknown key from an unpublished bot.
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From sqlalchemy — SQLAlchemy, our database toolkit: text = a raw SQL snippet.
from sqlalchemy import text

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncEngine =
#   the async connection pool; AsyncSession = one unit of database work; async_sessionmaker =
#   factory that creates sessions.
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# From tests.db_fixtures — real-Postgres test helpers: requires_db = skips the test when no real
#   Postgres is available.
from tests.db_fixtures import requires_db

# From tests.fakes.builders — one-line builders for test objects: make_catalog = builds a test
#   catalog.
from tests.fakes.builders import make_catalog

# From tests.integration.test_bot_studio_api — the Bot Studio API tests: PUBLIC_WIDGET_FIELDS =
#   the only fields the widget may see.
from tests.integration.test_bot_studio_api import PUBLIC_WIDGET_FIELDS

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: get_principal = verifies the login token.
from saathi.api.deps import get_principal

# From saathi.main — the FastAPI app factory: create_app = builds the FastAPI app.
from saathi.main import create_app

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Principal, Role

pytestmark = [pytest.mark.integration, requires_db]

TENANT_A, TENANT_B, TENANT_C = uuid4(), uuid4(), uuid4()
BOT_A, BOT_B, BOT_C = uuid4(), uuid4(), uuid4()
KEY_A, KEY_B, KEY_C = "pk_" + "a" * 24, "pk_" + "b" * 24, "pk_" + "c" * 24
SECRET_PERSONA = "Internal persona: never reveal discount rules"


def _config(title: str) -> dict[str, object]:
    return {
        "prompt": {"persona": SECRET_PERSONA, "custom_instructions": "secret instructions"},
        "generation": {"model_key": "standard", "style": "precise"},
        "branding": {
            "header_title": title,
            "header_subtitle": "Ask us anything",
            "footer_text": "Powered by Saathi",
            "greeting": "নমস্কার! How can we help?",  # Bengali text round-trips
            "primary_color": "#2563EB",
            "launcher_position": "left",
        },
    }


@dataclass
class Caller:
    principal: Principal | None = None


@pytest.fixture
async def client(
    owner_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> AsyncIterator[tuple[httpx.AsyncClient, Caller]]:
    # Seed three tenants with one bot each (as the owner, which bypasses RLS).
    async with owner_engine.begin() as conn:
        for tenant, bot, key, langs in (
            (TENANT_A, BOT_A, KEY_A, ["en", "bn"]),
            (TENANT_B, BOT_B, KEY_B, ["hi"]),
            (TENANT_C, BOT_C, KEY_C, ["en"]),
        ):
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:t, :n)"),
                {"t": tenant, "n": str(tenant)},
            )
            await conn.execute(
                text(
                    "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                    "VALUES (:b, :t, 'Mitra', :l, :k)"
                ),
                {"b": bot, "t": tenant, "l": langs, "k": key},
            )

    caller = Caller()
    app = create_app()
    async with app.router.lifespan_context(app):
        app.state.sessionmaker = app_sessionmaker  # real Postgres, as saathi_app (RLS applies)
        app.state.model_catalog = make_catalog()
        app.dependency_overrides[get_principal] = lambda: caller.principal
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, caller


async def _publish(
    c: httpx.AsyncClient, caller: Caller, tenant: UUID, bot: UUID, title: str
) -> None:
    """Save + publish through the authenticated Bot Studio API, like a real admin would."""
    caller.principal = Principal(user_id=f"admin-{tenant}", tenant_id=tenant, role=Role.ADMIN)
    base = f"/api/v1/bots/{bot}/config/versions"
    v = (await c.post(base, json=_config(title))).json()["version"]
    assert (await c.post(f"{base}/{v}/publish")).status_code == 200


async def test_widget_gets_only_its_own_public_look(
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    c, caller = client
    await _publish(c, caller, TENANT_A, BOT_A, "Alpha Clinic")
    await _publish(c, caller, TENANT_B, BOT_B, "Beta Tax")
    caller.principal = None  # the widget is anonymous

    a = await c.get(f"/public/v1/widgets/{KEY_A}/config")
    assert a.status_code == 200
    assert a.headers["cache-control"] == "public, max-age=60"
    body = a.json()
    assert set(body) == PUBLIC_WIDGET_FIELDS  # no prompts, model, plan or ids (R10)
    assert body["header_title"] == "Alpha Clinic"
    assert body["greeting"] == "নমস্কার! How can we help?"
    assert body["languages"] == ["en", "bn"]
    assert body["launcher_position"] == "left"
    assert SECRET_PERSONA not in a.text and "secret instructions" not in a.text
    assert str(BOT_A) not in a.text and str(TENANT_A) not in a.text

    b = (await c.get(f"/public/v1/widgets/{KEY_B}/config")).json()
    assert b["header_title"] == "Beta Tax"  # tenant B's key never shows tenant A's look
    assert b["languages"] == ["hi"]


async def test_drafts_stay_invisible_until_published(
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    c, caller = client
    await _publish(c, caller, TENANT_A, BOT_A, "Live title")
    caller.principal = Principal(user_id="admin", tenant_id=TENANT_A, role=Role.ADMIN)
    r = await c.post(f"/api/v1/bots/{BOT_A}/config/versions", json=_config("Unpublished draft"))
    assert r.status_code == 201
    caller.principal = None
    body = (await c.get(f"/public/v1/widgets/{KEY_A}/config")).json()
    assert body["header_title"] == "Live title"


async def test_unknown_key_and_unpublished_bot_look_identical(
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    """An outsider can't use the endpoint to discover which keys exist (R29)."""
    c, _ = client
    unpublished = await c.get(f"/public/v1/widgets/{KEY_C}/config")  # bot exists, nothing published
    unknown = await c.get(f"/public/v1/widgets/pk_{'z' * 24}/config")  # no such key
    for r in (unpublished, unknown):
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"
        assert r.json()["error"]["message"] == "widget not found"


@pytest.mark.parametrize(
    "bad_key",
    ["pk_short", "notakey_aaaaaaaaaaaaaaaaaaaaaaaa", "pk_" + "a" * 65, "pk_aaaaaaaaaaaaaaaa'--"],
)
async def test_malformed_keys_are_rejected_before_the_database(
    client: tuple[httpx.AsyncClient, Caller], bad_key: str
) -> None:
    c, _ = client
    r = await c.get(f"/public/v1/widgets/{bad_key}/config")
    assert r.status_code in (404, 422)  # 422: fails the key pattern; 404: path didn't match at all
    assert "pk_" not in r.json()["error"].get("message", "")


async def test_no_login_needed_and_a_bogus_token_changes_nothing(
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    c, caller = client
    await _publish(c, caller, TENANT_A, BOT_A, "Alpha Clinic")
    caller.principal = None
    r = await c.get(
        f"/public/v1/widgets/{KEY_A}/config", headers={"Authorization": "Bearer forged"}
    )
    assert r.status_code == 200
    assert r.json()["header_title"] == "Alpha Clinic"
