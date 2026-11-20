# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The /api/v1/bots endpoints (create, list, read, update, delete;
#                401/403/404/422).
# How to run: cd backend && uv run pytest tests/integration (no real database: services are
#             swapped for in-memory fakes).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Route tests with the use-case service swapped for an in-memory repository (no DB).

Possible only because routes depend on BotService via `get_bot_service` (Dependency Inversion).
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: make_bot = builds a test bot.
from tests.fakes.builders import make_bot

# From tests.fakes.in_memory — in-memory stand-ins for the database stores:
#   InMemoryBotRepository = bots in a dict.
from tests.fakes.in_memory import InMemoryBotRepository

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: get_principal = verifies the login token.
from saathi.api.deps import get_principal

# From saathi.main — the FastAPI app factory: create_app = builds the FastAPI app.
from saathi.main import create_app

# From saathi.modules.tenancy.api.deps — builds the tenancy services per request:
#   get_bot_service = builds a BotService.
from saathi.modules.tenancy.api.deps import get_bot_service

# From saathi.modules.tenancy.application.services — the bot use cases: BotService = the bot use
#   cases.
from saathi.modules.tenancy.application.services import BotService

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Principal, Role

# The test tenant 'A'.
TENANT_A = UUID("00000000-0000-0000-0000-00000000000a")


# Holds what a test may change: the storage and the logged-in caller.
class Harness:
    # Set up:
    def __init__(self) -> None:
        # an empty in-memory bot storage,
        self.repo = InMemoryBotRepository()
        # an admin of tenant A as the caller.
        self.principal = Principal(user_id="u1", tenant_id=TENANT_A, role=Role.ADMIN)


# A fixture: the real app, with login and storage swapped for test versions.
@pytest.fixture
# It gives each test (client, harness).
async def ctx() -> AsyncIterator[tuple[httpx.AsyncClient, Harness]]:
    # A fresh harness.
    h = Harness()
    # The real app.
    app = create_app()
    # Skip real login checking: 'the caller is whoever the harness says'.
    app.dependency_overrides[get_principal] = lambda: h.principal
    # Use the in-memory storage instead of the database.
    app.dependency_overrides[get_bot_service] = lambda: BotService(h.repo)
    # Run the app's start-up (and shutdown afterwards).
    async with app.router.lifespan_context(app):
        # Send requests straight into the app.
        transport = httpx.ASGITransport(app=app)
        # A client using that.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Lend both to the test.
            yield client, h


# 🔒 The new bot's tenant comes from the login, not from the request.
async def test_create_bot_takes_tenant_from_token(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack the fixture.
    client, h = ctx
    # Create a bot.
    r = await client.post("/api/v1/bots", json={"name": "Mitra", "languages": ["en", "bn"]})
    # 201 Created.
    assert r.status_code == 201
    # Find what was stored.
    stored = h.repo.rows[UUID(r.json()["id"])]
    # It belongs to the caller's tenant.
    assert stored.tenant_id == TENANT_A
    # It got a widget key.
    assert r.json()["public_key"].startswith("pk_")


# 🔒 Sending a tenant_id in the body is refused.
async def test_smuggled_tenant_id_is_rejected(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack (harness not needed).
    client, _ = ctx
    # Try to create a bot in a random other tenant.
    r = await client.post(
        "/api/v1/bots", json={"name": "x", "languages": ["en"], "tenant_id": str(uuid4())}
    )
    # 422.
    assert r.status_code == 422
    # With our validation error code.
    assert r.json()["error"]["code"] == "validation_error"


# 🔒 Viewers can't create bots.
async def test_viewer_cannot_create(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack.
    client, h = ctx
    # Log in as a viewer instead.
    h.principal = Principal(user_id="u2", tenant_id=TENANT_A, role=Role.VIEWER)
    # Try to create.
    r = await client.post("/api/v1/bots", json={"name": "x", "languages": ["en"]})
    # 403.
    assert r.status_code == 403


# 🔒 Another tenant's bot looks like it doesn't exist.
async def test_other_tenants_bot_is_404(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack.
    client, h = ctx
    # A bot in a different tenant...
    other = make_bot(tenant_id=uuid4(), name="B")
    # ...saved in the in-memory storage.
    await h.repo.add(other)
    # Ask for it as tenant A.
    r = await client.get(f"/api/v1/bots/{other.id}")
    # 404.
    assert r.status_code == 404


# ----------------------------------------------------------------- P1.8: update and delete
async def test_create_duplicate_name_is_409(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack.
    client, _ = ctx
    # The request body.
    body = {"name": "Mitra", "languages": ["en"]}
    # First create works.
    assert (await client.post("/api/v1/bots", json=body)).status_code == 201
    # Second create with the same name...
    r = await client.post("/api/v1/bots", json=body)
    # ...409.
    assert r.status_code == 409
    # With the conflict code.
    assert r.json()["error"]["code"] == "conflict"


# PATCH changes only the fields sent.
async def test_patch_updates_only_sent_fields(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack.
    client, h = ctx
    # A test bot in tenant A...
    bot = make_bot(tenant_id=TENANT_A, name="Mitra")
    # ...saved in the in-memory storage.
    await h.repo.add(bot)
    # Change the name (in Bengali) and the languages.
    r = await client.patch(f"/api/v1/bots/{bot.id}", json={"name": "মিত্র", "languages": ["bn"]})
    # 200.
    assert r.status_code == 200
    assert r.json()["name"] == "মিত্র"  # Bengali names round-trip
    # Languages changed.
    assert r.json()["languages"] == ["bn"]
    assert r.json()["public_key"] == bot.public_key  # untouched
    # Persona unchanged.
    assert h.repo.rows[bot.id].persona == bot.persona


# Run once per bad PATCH body below:
@pytest.mark.parametrize(
    # each case provides `body`,
    "body",
    # the cases:
    [
        {},  # nothing to change
        {"name": None},  # explicit null
        # empty name,
        {"name": ""},
        # name too long,
        {"name": "x" * 101},
        # no languages,
        {"languages": []},
        # unsupported language,
        {"languages": ["fr"]},
        {"tenant_id": str(uuid4())},  # smuggled tenant
        {"public_key": "pk_aaaaaaaaaaaaaaaaaaaa"},  # keys are server-generated
    ],
)
# Every one of them gives 422.
async def test_patch_rejects_bad_input(
    ctx: tuple[httpx.AsyncClient, Harness], body: dict[str, object]
) -> None:
    # Unpack.
    client, h = ctx
    # A test bot in tenant A...
    bot = make_bot(tenant_id=TENANT_A)
    # ...saved in the in-memory storage.
    await h.repo.add(bot)
    # Send the bad body.
    r = await client.patch(f"/api/v1/bots/{bot.id}", json=body)
    # 422.
    assert r.status_code == 422


# Renaming to a name already used gives 409.
async def test_patch_to_existing_name_is_409(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack.
    client, h = ctx
    # Two bots, A and B.
    a, b = make_bot(tenant_id=TENANT_A, name="A"), make_bot(tenant_id=TENANT_A, name="B")
    # Save A.
    await h.repo.add(a)
    # Save B.
    await h.repo.add(b)
    # Rename B to 'A'.
    r = await client.patch(f"/api/v1/bots/{b.id}", json={"name": "A"})
    # 409.
    assert r.status_code == 409


# 🔒 Changing or deleting another tenant's bot gives 404.
async def test_patch_and_delete_other_tenants_bot_are_404(
    # (uses the fixture)
    ctx: tuple[httpx.AsyncClient, Harness],
) -> None:
    # Unpack.
    client, h = ctx
    # A bot in another tenant...
    other = make_bot(tenant_id=uuid4(), name="Theirs")
    # ...saved in the in-memory storage.
    await h.repo.add(other)
    # PATCH -> 404.
    assert (await client.patch(f"/api/v1/bots/{other.id}", json={"name": "x"})).status_code == 404
    # DELETE -> 404.
    assert (await client.delete(f"/api/v1/bots/{other.id}")).status_code == 404
    assert h.repo.rows[other.id].name == "Theirs"  # untouched


# 🔒 Viewers can't change or delete.
async def test_viewer_cannot_patch_or_delete(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack.
    client, h = ctx
    # A test bot in tenant A...
    bot = make_bot(tenant_id=TENANT_A)
    # ...saved in the in-memory storage.
    await h.repo.add(bot)
    # Log in as a viewer.
    h.principal = Principal(user_id="u2", tenant_id=TENANT_A, role=Role.VIEWER)
    # PATCH -> 403.
    assert (await client.patch(f"/api/v1/bots/{bot.id}", json={"name": "x"})).status_code == 403
    # DELETE -> 403.
    assert (await client.delete(f"/api/v1/bots/{bot.id}")).status_code == 403
    # The bot is still there.
    assert bot.id in h.repo.rows


# Deleting works, and deleting again gives 404.
async def test_delete_bot(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Unpack.
    client, h = ctx
    # A test bot in tenant A...
    bot = make_bot(tenant_id=TENANT_A)
    # ...saved in the in-memory storage.
    await h.repo.add(bot)
    # Delete it.
    r = await client.delete(f"/api/v1/bots/{bot.id}")
    # 204 No Content.
    assert r.status_code == 204
    # Empty body.
    assert r.content == b""
    # Gone from storage.
    assert bot.id not in h.repo.rows
    # Deleting again -> 404.
    assert (await client.delete(f"/api/v1/bots/{bot.id}")).status_code == 404


# 🔒 PATCH and DELETE need a login too.
async def test_new_endpoints_require_login() -> None:
    app = create_app()  # no principal override: real dependency, no verifier -> 401
    # Run start-up.
    async with app.router.lifespan_context(app):
        # Send requests straight into the app.
        transport = httpx.ASGITransport(app=app)
        # A client.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Any bot id.
            bot_id = uuid4()
            # PATCH without login...
            assert (
                await client.patch(f"/api/v1/bots/{bot_id}", json={"name": "x"})
            ).status_code == 401
            # DELETE without login -> 401.
            assert (await client.delete(f"/api/v1/bots/{bot_id}")).status_code == 401
