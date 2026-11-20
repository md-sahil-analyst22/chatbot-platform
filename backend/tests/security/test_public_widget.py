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

# Every test in this file is an integration test and needs the real database.
pytestmark = [pytest.mark.integration, requires_db]

# Three test tenants.
TENANT_A, TENANT_B, TENANT_C = uuid4(), uuid4(), uuid4()
# One bot each.
BOT_A, BOT_B, BOT_C = uuid4(), uuid4(), uuid4()
# Their widget keys.
KEY_A, KEY_B, KEY_C = "pk_" + "a" * 24, "pk_" + "b" * 24, "pk_" + "c" * 24
# Private text that must never appear in a public answer.
SECRET_PERSONA = "Internal persona: never reveal discount rules"


# Helper: a config body with private text and the given title.
def _config(title: str) -> dict[str, object]:
    # The body:
    return {
        # private persona and instructions,
        "prompt": {"persona": SECRET_PERSONA, "custom_instructions": "secret instructions"},
        # model and style,
        "generation": {"model_key": "standard", "style": "precise"},
        # branding:
        "branding": {
            # the title,
            "header_title": title,
            # a subtitle,
            "header_subtitle": "Ask us anything",
            # a footer,
            "footer_text": "Powered by Saathi",
            "greeting": "নমস্কার! How can we help?",  # Bengali text round-trips
            # a colour,
            "primary_color": "#2563EB",
            # launcher on the left.
            "launcher_position": "left",
        },
    }


# @dataclass writes __init__ for us.
@dataclass
# Who the test is logged in as (None = anonymous).
class Caller:
    # Starts anonymous.
    principal: Principal | None = None


# A fixture: the real app on the real database, as saathi_app.
@pytest.fixture
# It gives each test (client, caller).
async def client(
    owner_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> AsyncIterator[tuple[httpx.AsyncClient, Caller]]:
    # Seed three tenants with one bot each (as the owner, which bypasses RLS).
    async with owner_engine.begin() as conn:
        # For each of the three (tenant, bot, key, languages):
        for tenant, bot, key, langs in (
            # tenant A: English + Bengali,
            (TENANT_A, BOT_A, KEY_A, ["en", "bn"]),
            # tenant B: Hindi,
            (TENANT_B, BOT_B, KEY_B, ["hi"]),
            # tenant C: English (never published).
            (TENANT_C, BOT_C, KEY_C, ["en"]),
        ):
            # Insert the tenant...
            await conn.execute(
                # (the SQL)
                text("INSERT INTO tenants (id, name) VALUES (:t, :n)"),
                # (its values)
                {"t": tenant, "n": str(tenant)},
            )
            # ...and its bot.
            await conn.execute(
                # (the SQL)
                text(
                    "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                    "VALUES (:b, :t, 'Mitra', :l, :k)"
                ),
                # (its values)
                {"b": bot, "t": tenant, "l": langs, "k": key},
            )

    # Start anonymous.
    caller = Caller()
    # The real app.
    app = create_app()
    # Run start-up.
    async with app.router.lifespan_context(app):
        app.state.sessionmaker = app_sessionmaker  # real Postgres, as saathi_app (RLS applies)
        # The test catalog.
        app.state.model_catalog = make_catalog()
        # Skip login: the caller is whoever the test sets.
        app.dependency_overrides[get_principal] = lambda: caller.principal
        # Send requests straight into the app.
        transport = httpx.ASGITransport(app=app)
        # A client.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            # Lend the client and the caller to the test.
            yield c, caller


# Helper: log in as an admin of `tenant`, save a config titled `title` and publish it.
async def _publish(
    c: httpx.AsyncClient, caller: Caller, tenant: UUID, bot: UUID, title: str
) -> None:
    """Save + publish through the authenticated Bot Studio API, like a real admin would."""
    # Become that tenant's admin.
    caller.principal = Principal(user_id=f"admin-{tenant}", tenant_id=tenant, role=Role.ADMIN)
    # The bot's versions address.
    base = f"/api/v1/bots/{bot}/config/versions"
    # Save a draft and get its version number.
    v = (await c.post(base, json=_config(title))).json()["version"]
    # Publish it; must succeed.
    assert (await c.post(f"{base}/{v}/publish")).status_code == 200


# 🔒 Each widget key shows only its own tenant's public look.
async def test_widget_gets_only_its_own_public_look(
    # (uses the fixture)
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    # Unpack.
    c, caller = client
    # Publish tenant A's look.
    await _publish(c, caller, TENANT_A, BOT_A, "Alpha Clinic")
    # Publish tenant B's look.
    await _publish(c, caller, TENANT_B, BOT_B, "Beta Tax")
    caller.principal = None  # the widget is anonymous

    # Read A's widget config.
    a = await c.get(f"/public/v1/widgets/{KEY_A}/config")
    # 200.
    assert a.status_code == 200
    # Cacheable for 60 seconds.
    assert a.headers["cache-control"] == "public, max-age=60"
    # The body.
    body = a.json()
    assert set(body) == PUBLIC_WIDGET_FIELDS  # no prompts, model, plan or ids (R10)
    # A's title.
    assert body["header_title"] == "Alpha Clinic"
    # The Bengali greeting is intact.
    assert body["greeting"] == "নমস্কার! How can we help?"
    # A's languages.
    assert body["languages"] == ["en", "bn"]
    # A's launcher side.
    assert body["launcher_position"] == "left"
    # No private text.
    assert SECRET_PERSONA not in a.text and "secret instructions" not in a.text
    # No internal ids.
    assert str(BOT_A) not in a.text and str(TENANT_A) not in a.text

    # Read B's widget config.
    b = (await c.get(f"/public/v1/widgets/{KEY_B}/config")).json()
    assert b["header_title"] == "Beta Tax"  # tenant B's key never shows tenant A's look
    # B's languages.
    assert b["languages"] == ["hi"]


# Unpublished drafts never reach the widget.
async def test_drafts_stay_invisible_until_published(
    # (uses the fixture)
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    # Unpack.
    c, caller = client
    # Publish a live title.
    await _publish(c, caller, TENANT_A, BOT_A, "Live title")
    # Log in as tenant A's admin.
    caller.principal = Principal(user_id="admin", tenant_id=TENANT_A, role=Role.ADMIN)
    # Save a newer draft without publishing.
    r = await c.post(f"/api/v1/bots/{BOT_A}/config/versions", json=_config("Unpublished draft"))
    # Saved.
    assert r.status_code == 201
    # Back to anonymous.
    caller.principal = None
    # Read the widget config.
    body = (await c.get(f"/public/v1/widgets/{KEY_A}/config")).json()
    # Still the live title.
    assert body["header_title"] == "Live title"


# 🔒 Unknown keys and unpublished bots look the same (nothing is revealed).
async def test_unknown_key_and_unpublished_bot_look_identical(
    # (uses the fixture)
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    """An outsider can't use the endpoint to discover which keys exist (R29)."""
    # Unpack.
    c, _ = client
    unpublished = await c.get(f"/public/v1/widgets/{KEY_C}/config")  # bot exists, nothing published
    unknown = await c.get(f"/public/v1/widgets/pk_{'z' * 24}/config")  # no such key
    # For both answers:
    for r in (unpublished, unknown):
        # 404,
        assert r.status_code == 404
        # the same code,
        assert r.json()["error"]["code"] == "not_found"
        # the same message.
        assert r.json()["error"]["message"] == "widget not found"


# Run once per malformed key:
@pytest.mark.parametrize(
    # each case provides `bad_key`,
    "bad_key",
    # too short, wrong prefix, too long, and an SQL-injection attempt.
    ["pk_short", "notakey_aaaaaaaaaaaaaaaaaaaaaaaa", "pk_" + "a" * 65, "pk_aaaaaaaaaaaaaaaa'--"],
)
# 🔒 Malformed keys are refused before any database lookup.
async def test_malformed_keys_are_rejected_before_the_database(
    client: tuple[httpx.AsyncClient, Caller], bad_key: str
) -> None:
    # Unpack.
    c, _ = client
    # Request with the bad key.
    r = await c.get(f"/public/v1/widgets/{bad_key}/config")
    assert r.status_code in (404, 422)  # 422: fails the key pattern; 404: path didn't match at all
    # The key isn't echoed back in the message.
    assert "pk_" not in r.json()["error"].get("message", "")


# No login is needed, and a fake token neither helps nor breaks anything.
async def test_no_login_needed_and_a_bogus_token_changes_nothing(
    # (uses the fixture)
    client: tuple[httpx.AsyncClient, Caller],
) -> None:
    # Unpack.
    c, caller = client
    # Publish A's look.
    await _publish(c, caller, TENANT_A, BOT_A, "Alpha Clinic")
    # Anonymous.
    caller.principal = None
    # Request with a forged token...
    r = await c.get(
        f"/public/v1/widgets/{KEY_A}/config", headers={"Authorization": "Bearer forged"}
    )
    # Still 200.
    assert r.status_code == 200
    # The normal public answer.
    assert r.json()["header_title"] == "Alpha Clinic"
