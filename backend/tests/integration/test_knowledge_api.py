# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The knowledge endpoints (sources and FAQs) with in-memory services: every
#                endpoint is checked for no login (401), wrong role (403), another tenant's bot
#                (404) and bad input (422) (R36), plus the upload size limit enforced before the
#                body is read.
# How to run: cd backend && uv run pytest tests/integration/test_knowledge_api.py (no database:
#             services are swapped for in-memory fakes).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""/api/v1/bots/{bot_id}/sources and /faqs."""

# From collections.abc — standard type names: AsyncIterator = something looped with
#   `async for`.
from collections.abc import AsyncIterator

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# httpx — the HTTP client used to call the app in-process.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.knowledge — in-memory stand-ins for the knowledge ports.
from tests.fakes.knowledge import (
    FakeBotDirectory,
    InMemoryFaqRepository,
    InMemorySourceRepository,
    RecordingPostCommit,
    RecordingQueue,
)

# From tests.fakes.providers — FakeEmbedder; InMemoryObjectStore.
from tests.fakes.providers import FakeEmbedder, InMemoryObjectStore

# From saathi.api.deps — get_principal = verifies the login token (overridden in most tests).
from saathi.api.deps import get_principal

# From saathi.main — create_app = builds the FastAPI app.
from saathi.main import create_app

# From saathi.modules.knowledge.api.deps — the service builders the routes ask for.
from saathi.modules.knowledge.api.deps import get_faq_service, get_source_service

# From saathi.modules.knowledge.application.faq_service — FaqService.
from saathi.modules.knowledge.application.faq_service import FaqService

# From saathi.modules.knowledge.application.source_service — SourceService.
from saathi.modules.knowledge.application.source_service import SourceService

# From saathi.platform.security.auth — Principal = the verified caller; Role.
from saathi.platform.security.auth import Principal, Role

# The test tenant 'A'.
TENANT = UUID("00000000-0000-0000-0000-00000000000a")
# Tenant A's bot.
BOT = uuid4()


# What a test may change: the caller, and the fakes behind the services.
class Harness:
    """Fakes wired into the real services."""

    # Build it.
    def __init__(self) -> None:
        # Logged in as an admin of tenant A (tests may change this).
        self.principal = Principal(user_id="u1", tenant_id=TENANT, role=Role.ADMIN)
        # Only tenant A's BOT exists.
        bots = FakeBotDirectory({(TENANT, BOT)})
        # Source storage.
        self.sources = InMemorySourceRepository()
        # Records queued jobs.
        self.queue = RecordingQueue()
        # File storage.
        self.store = InMemoryObjectStore()
        # The real source service on the fakes.
        self.source_service = SourceService(
            sources=self.sources,
            bots=bots,
            store=self.store,
            queue=self.queue,
            post_commit=RecordingPostCommit(),
        )
        # The real FAQ service on the fakes.
        self.faq_service = FaqService(
            faqs=InMemoryFaqRepository(), bots=bots, embedder=FakeEmbedder()
        )


# A test client for the app with the services swapped for the harness.
@pytest.fixture
async def ctx() -> AsyncIterator[tuple[httpx.AsyncClient, Harness]]:
    # The fakes.
    h = Harness()
    # The real app.
    app = create_app()
    # 'Who is calling' = the harness's principal.
    app.dependency_overrides[get_principal] = lambda: h.principal
    # The routes get the harness's source service...
    app.dependency_overrides[get_source_service] = lambda: h.source_service
    # ...and FAQ service.
    app.dependency_overrides[get_faq_service] = lambda: h.faq_service
    # Run the app's startup/shutdown around the test.
    async with app.router.lifespan_context(app):
        # Call the app in-process (no network).
        transport = httpx.ASGITransport(app=app)
        # The client.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Hand both to the test.
            yield client, h


# 📤 Upload: 202, queued, and the storage key never leaks.
async def test_upload_is_accepted_and_queued(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Client and fakes.
    client, h = ctx
    # Upload a Markdown file.
    r = await client.post(
        f"/api/v1/bots/{BOT}/sources/upload",
        files={"file": ("Fees.md", "# Fees\nGST ₹500".encode(), "text/markdown")},
    )
    # Accepted for background processing.
    assert r.status_code == 202
    # The response body.
    body = r.json()
    # Queued file source with its original name.
    assert body["status"] == "queued" and body["kind"] == "file" and body["title"] == "Fees.md"
    # The storage key (which contains the tenant id) is not in the response.
    assert "uri" not in body and str(TENANT) not in r.text
    # One job was queued.
    assert len(h.queue.jobs) == 1


# An unsupported file type is 422 in the standard error shape.
async def test_upload_of_an_unsupported_file_is_422(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Client.
    client, _ = ctx
    # Upload an SVG (can carry scripts).
    r = await client.post(
        f"/api/v1/bots/{BOT}/sources/upload",
        files={"file": ("x.svg", b"<svg onload=1>", "image/svg+xml")},
    )
    # 422 with our error code.
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# 🔒 A declared size over 20 MB is refused before the body is read.
async def test_oversized_upload_is_413_before_reading(
    ctx: tuple[httpx.AsyncClient, Harness],
) -> None:
    # Client and fakes.
    client, h = ctx
    # Claim 30 MB (only 1 byte is actually sent).
    r = await client.post(
        f"/api/v1/bots/{BOT}/sources/upload",
        content=b"x",
        headers={
            "content-type": "multipart/form-data; boundary=b",
            "content-length": str(30 * 1024 * 1024),
        },
    )
    # 413 with our error code.
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    # The error carries the request id; nothing was queued.
    assert r.json()["error"]["request_id"] and h.queue.jobs == []


# 🔒 An upload that doesn't declare its size is refused.
async def test_upload_without_declared_size_is_411(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Client.
    client, _ = ctx

    # A streamed body (sent without Content-Length).
    async def body() -> AsyncIterator[bytes]:
        # One piece.
        yield b"--b\r\n"

    # Send it.
    r = await client.post(
        f"/api/v1/bots/{BOT}/sources/upload",
        content=body(),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    # 411 Length Required.
    assert r.status_code == 411


# 🕸️ Crawl: valid settings accepted; smuggled tenant id and bad values are 422.
async def test_crawl_validation_and_smuggled_tenant(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Client.
    client, _ = ctx
    # Valid settings.
    ok = await client.post(
        f"/api/v1/bots/{BOT}/sources/crawl", json={"url": "https://shop.example/", "max_depth": 2}
    )
    # Accepted, settings echoed.
    assert ok.status_code == 202 and ok.json()["crawl"]["max_depth"] == 2
    # Each of these bodies is invalid...
    for bad in (
        # 🔒 a smuggled tenant id (R8);
        {"url": "https://shop.example/", "tenant_id": str(uuid4())},
        # not a web address;
        {"url": "ftp://shop.example/"},
        # too deep;
        {"url": "https://shop.example/", "max_depth": 9},
        # a pattern without '/';
        {"url": "https://shop.example/", "include_patterns": ["no-slash"]},
        # too many patterns.
        {"url": "https://shop.example/", "exclude_patterns": ["/x"] * 21},
    ):
        # Send it.
        r = await client.post(f"/api/v1/bots/{BOT}/sources/crawl", json=bad)
        # 422.
        assert r.status_code == 422, bad


# The full source life through HTTP: list, get, re-sync, delete.
async def test_list_get_resync_delete(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Client.
    client, _ = ctx
    # Upload a file.
    created = (
        await client.post(
            f"/api/v1/bots/{BOT}/sources/upload", files={"file": ("a.txt", b"hello", "text/plain")}
        )
    ).json()
    # List the bot's sources.
    listed = (await client.get(f"/api/v1/bots/{BOT}/sources")).json()
    # Exactly that source, with no chunks yet.
    assert [s["id"] for s in listed] == [created["id"]] and listed[0]["chunk_count"] == 0
    # Read it: 200.
    assert (await client.get(f"/api/v1/bots/{BOT}/sources/{created['id']}")).status_code == 200
    # Re-sync it: 202.
    assert (
        await client.post(f"/api/v1/bots/{BOT}/sources/{created['id']}/resync")
    ).status_code == 202
    # Delete it: 204.
    assert (await client.delete(f"/api/v1/bots/{BOT}/sources/{created['id']}")).status_code == 204
    # Gone: 404.
    assert (await client.get(f"/api/v1/bots/{BOT}/sources/{created['id']}")).status_code == 404


# Viewers can read but not change anything (403).
async def test_viewer_can_read_but_not_change(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Client and fakes.
    client, h = ctx
    # Log in as a viewer.
    h.principal = Principal(user_id="v", tenant_id=TENANT, role=Role.VIEWER)
    # Listing sources: allowed.
    assert (await client.get(f"/api/v1/bots/{BOT}/sources")).status_code == 200
    # Listing FAQs: allowed.
    assert (await client.get(f"/api/v1/bots/{BOT}/faqs")).status_code == 200
    # Uploading...
    r = await client.post(
        f"/api/v1/bots/{BOT}/sources/upload", files={"file": ("a.txt", b"x", "text/plain")}
    )
    # ...forbidden.
    assert r.status_code == 403
    # Adding a website: forbidden.
    assert (
        await client.post(f"/api/v1/bots/{BOT}/sources/crawl", json={"url": "https://a.example/"})
    ).status_code == 403
    # Adding an FAQ: forbidden.
    assert (
        await client.post(f"/api/v1/bots/{BOT}/faqs", json={"question": "q", "answer": "a"})
    ).status_code == 403


# 🔒 Another tenant's (or an unknown) bot is 404 on every endpoint.
async def test_another_tenants_bot_is_404_everywhere(
    ctx: tuple[httpx.AsyncClient, Harness],
) -> None:
    # Client.
    client, _ = ctx
    # A bot id that isn't ours.
    other = uuid4()
    # Listing its sources: 404.
    assert (await client.get(f"/api/v1/bots/{other}/sources")).status_code == 404
    # Listing its FAQs: 404.
    assert (await client.get(f"/api/v1/bots/{other}/faqs")).status_code == 404
    # Uploading to it...
    r = await client.post(
        f"/api/v1/bots/{other}/sources/upload", files={"file": ("a.txt", b"x", "text/plain")}
    )
    # ...404.
    assert r.status_code == 404
    # Adding an FAQ to it: 404.
    assert (
        await client.post(f"/api/v1/bots/{other}/faqs", json={"question": "q", "answer": "a"})
    ).status_code == 404
    # An unknown source of our own bot: 404.
    assert (await client.get(f"/api/v1/bots/{BOT}/sources/{uuid4()}")).status_code == 404


# ⭐ FAQ create/update/delete and input checks.
async def test_faq_crud_and_validation(ctx: tuple[httpx.AsyncClient, Harness]) -> None:
    # Client.
    client, _ = ctx
    # Create a Bengali FAQ.
    created = await client.post(
        f"/api/v1/bots/{BOT}/faqs", json={"question": "অফিস কখন খোলা?", "answer": "সকাল ১০টা"}
    )
    # 201, text round-trips.
    assert created.status_code == 201 and created.json()["question"] == "অফিস কখন খোলা?"
    # Its id.
    fid = created.json()["id"]
    # Switch it off.
    patched = await client.patch(f"/api/v1/bots/{BOT}/faqs/{fid}", json={"is_active": False})
    # 200, now off.
    assert patched.status_code == 200 and patched.json()["is_active"] is False
    # Each of these PATCH bodies is invalid...
    for bad in (
        # nothing to change;
        {},
        # explicit null;
        {"answer": None},
        # empty question;
        {"question": ""},
        # answer too long;
        {"answer": "a" * 4001},
        # 🔒 a smuggled tenant id.
        {"tenant_id": str(TENANT)},
    ):
        # ...422.
        assert (
            await client.patch(f"/api/v1/bots/{BOT}/faqs/{fid}", json=bad)
        ).status_code == 422, bad
    # A question that is too long: 422.
    assert (
        await client.post(f"/api/v1/bots/{BOT}/faqs", json={"question": "q" * 1001, "answer": "a"})
    ).status_code == 422
    # Delete: 204.
    assert (await client.delete(f"/api/v1/bots/{BOT}/faqs/{fid}")).status_code == 204
    # Delete again: 404.
    assert (await client.delete(f"/api/v1/bots/{BOT}/faqs/{fid}")).status_code == 404


# 🔒 Without a login every knowledge endpoint is 401 (fail closed, R16).
async def test_no_login_is_401() -> None:
    # The real app, with NO principal override: the real login check runs.
    app = create_app()
    # Startup/shutdown around the test, and an in-process client.
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        # A sample of endpoints and methods...
        for method, path in (
            ("GET", f"/api/v1/bots/{BOT}/sources"),
            ("POST", f"/api/v1/bots/{BOT}/sources/crawl"),
            ("GET", f"/api/v1/bots/{BOT}/faqs"),
            ("DELETE", f"/api/v1/bots/{BOT}/faqs/{uuid4()}"),
        ):
            # ...called without a token...
            r = await client.request(
                method, path, json={"url": "https://a.example/"} if method == "POST" else None
            )
            # ...is refused with 401.
            assert r.status_code == 401, path
