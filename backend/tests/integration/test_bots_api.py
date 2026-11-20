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

TENANT_A = UUID("00000000-0000-0000-0000-00000000000a")


class Harness:
    def __init__(self) -> None:
        self.repo = InMemoryBotRepository()
        self.principal = Principal(user_id="u1", tenant_id=TENANT_A, role=Role.ADMIN)


@pytest.fixture
async def ctx() -> AsyncIterator[tuple[httpx.AsyncClient, Harness]]:
    h = Harness()
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: h.principal
    app.dependency_overrides[get_bot_service] = lambda: BotService(h.repo)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, h


async def test_create_bot_takes_tenant_from_token(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, h = ctx
    r = await client.post("/api/v1/bots", json={"name": "Mitra", "languages": ["en", "bn"]})
    assert r.status_code == 201
    stored = h.repo.rows[UUID(r.json()["id"])]
    assert stored.tenant_id == TENANT_A
    assert r.json()["public_key"].startswith("pk_")


async def test_smuggled_tenant_id_is_rejected(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, _ = ctx
    r = await client.post(
        "/api/v1/bots", json={"name": "x", "languages": ["en"], "tenant_id": str(uuid4())}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_viewer_cannot_create(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, h = ctx
    h.principal = Principal(user_id="u2", tenant_id=TENANT_A, role=Role.VIEWER)
    r = await client.post("/api/v1/bots", json={"name": "x", "languages": ["en"]})
    assert r.status_code == 403


async def test_other_tenants_bot_is_404(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, h = ctx
    other = make_bot(tenant_id=uuid4(), name="B")
    await h.repo.add(other)
    r = await client.get(f"/api/v1/bots/{other.id}")
    assert r.status_code == 404


# ----------------------------------------------------------------- P1.8: update and delete
async def test_create_duplicate_name_is_409(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, _ = ctx
    body = {"name": "Mitra", "languages": ["en"]}
    assert (await client.post("/api/v1/bots", json=body)).status_code == 201
    r = await client.post("/api/v1/bots", json=body)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


async def test_patch_updates_only_sent_fields(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, h = ctx
    bot = make_bot(tenant_id=TENANT_A, name="Mitra")
    await h.repo.add(bot)
    r = await client.patch(f"/api/v1/bots/{bot.id}", json={"name": "মিত্র", "languages": ["bn"]})
    assert r.status_code == 200
    assert r.json()["name"] == "মিত্র"  # Bengali names round-trip
    assert r.json()["languages"] == ["bn"]
    assert r.json()["public_key"] == bot.public_key  # untouched
    assert h.repo.rows[bot.id].persona == bot.persona


@pytest.mark.parametrize(
    "body",
    [
        {},  # nothing to change
        {"name": None},  # explicit null
        {"name": ""},
        {"name": "x" * 101},
        {"languages": []},
        {"languages": ["fr"]},
        {"tenant_id": str(uuid4())},  # smuggled tenant
        {"public_key": "pk_aaaaaaaaaaaaaaaaaaaa"},  # keys are server-generated
    ],
)
async def test_patch_rejects_bad_input(
    ctx: tuple[httpx.AsyncClient, Harness], body: dict[str, object]
) -> None:
    client, h = ctx
    bot = make_bot(tenant_id=TENANT_A)
    await h.repo.add(bot)
    r = await client.patch(f"/api/v1/bots/{bot.id}", json=body)
    assert r.status_code == 422


async def test_patch_to_existing_name_is_409(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, h = ctx
    a, b = make_bot(tenant_id=TENANT_A, name="A"), make_bot(tenant_id=TENANT_A, name="B")
    await h.repo.add(a)
    await h.repo.add(b)
    r = await client.patch(f"/api/v1/bots/{b.id}", json={"name": "A"})
    assert r.status_code == 409


async def test_patch_and_delete_other_tenants_bot_are_404(
    ctx: tuple[httpx.AsyncClient, Harness],
) -> None:
    client, h = ctx
    other = make_bot(tenant_id=uuid4(), name="Theirs")
    await h.repo.add(other)
    assert (await client.patch(f"/api/v1/bots/{other.id}", json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/api/v1/bots/{other.id}")).status_code == 404
    assert h.repo.rows[other.id].name == "Theirs"  # untouched


async def test_viewer_cannot_patch_or_delete(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, h = ctx
    bot = make_bot(tenant_id=TENANT_A)
    await h.repo.add(bot)
    h.principal = Principal(user_id="u2", tenant_id=TENANT_A, role=Role.VIEWER)
    assert (await client.patch(f"/api/v1/bots/{bot.id}", json={"name": "x"})).status_code == 403
    assert (await client.delete(f"/api/v1/bots/{bot.id}")).status_code == 403
    assert bot.id in h.repo.rows


async def test_delete_bot(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    client, h = ctx
    bot = make_bot(tenant_id=TENANT_A)
    await h.repo.add(bot)
    r = await client.delete(f"/api/v1/bots/{bot.id}")
    assert r.status_code == 204
    assert r.content == b""
    assert bot.id not in h.repo.rows
    assert (await client.delete(f"/api/v1/bots/{bot.id}")).status_code == 404


async def test_new_endpoints_require_login() -> None:
    app = create_app()  # no principal override: real dependency, no verifier -> 401
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            bot_id = uuid4()
            assert (
                await client.patch(f"/api/v1/bots/{bot_id}", json={"name": "x"})
            ).status_code == 401
            assert (await client.delete(f"/api/v1/bots/{bot_id}")).status_code == 401
