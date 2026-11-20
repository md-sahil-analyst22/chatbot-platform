# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every file store must follow (put/get/delete, safe paths).
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
import httpx
import pytest
from tests.fakes.providers import InMemoryObjectStore

from saathi.platform.errors import NotFoundError, ProviderError, ValidationError
from saathi.platform.storage import ObjectStore
from saathi.platform.storage.supabase_store import SupabaseObjectStore

KEY = "t/tenant-1/docs/price-list.pdf"
BAD_KEYS = ["docs/a.pdf", "t/tenant-1", "t/tenant-1/../tenant-2/a.pdf", "/t/x/a", "t/x/a b.pdf"]


class ObjectStoreContract:
    def make(self, *, public: bool = False) -> ObjectStore:
        raise NotImplementedError

    async def test_put_then_get_round_trips(self) -> None:
        store = self.make()
        await store.put(KEY, b"%PDF-1.7", "application/pdf")
        assert await store.get(KEY) == b"%PDF-1.7"

    async def test_get_missing_raises_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            await self.make().get("t/tenant-1/docs/missing.pdf")

    async def test_delete_is_idempotent(self) -> None:
        store = self.make()
        await store.put(KEY, b"x", "text/plain")
        await store.delete(KEY)
        await store.delete(KEY)
        with pytest.raises(NotFoundError):
            await store.get(KEY)

    @pytest.mark.parametrize("key", BAD_KEYS)
    async def test_rejects_keys_without_tenant_prefix_or_with_traversal(self, key: str) -> None:
        with pytest.raises(ValidationError):
            await self.make().put(key, b"x", "text/plain")

    def test_private_store_has_no_public_url(self) -> None:
        assert self.make(public=False).public_url(KEY) is None

    def test_public_store_has_public_url(self) -> None:
        url = self.make(public=True).public_url(KEY)
        assert url is not None and url.endswith(KEY)


class TestInMemoryObjectStore(ObjectStoreContract):
    def make(self, *, public: bool = False) -> ObjectStore:
        return InMemoryObjectStore(public=public)


class TestSupabaseObjectStore(ObjectStoreContract):
    """Simulates the Supabase Storage REST API in memory."""

    requests: list[httpx.Request]

    def make(self, *, public: bool = False) -> ObjectStore:
        objects: dict[str, bytes] = {}
        prefix = "/storage/v1/object/bucket/"
        self.requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            assert request.headers["Authorization"] == "Bearer service-key"
            path = request.url.path
            assert path.startswith(prefix)
            key = path.removeprefix(prefix)
            if request.method == "POST":
                objects[key] = request.read()
                return httpx.Response(200, json={"Key": f"bucket/{key}"})
            if key not in objects:
                # Supabase reports missing objects as 400 + statusCode "404"
                return httpx.Response(400, json={"statusCode": "404", "error": "not_found"})
            if request.method == "GET":
                return httpx.Response(200, content=objects[key])
            del objects[key]
            return httpx.Response(200, json={"message": "deleted"})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return SupabaseObjectStore(
            http,
            project_url="https://proj.supabase.co",
            service_role_key="service-key",
            bucket="bucket",
            public=public,
        )

    async def test_upload_sends_content_type_and_upserts(self) -> None:
        await self.make().put(KEY, b"x", "application/pdf")
        sent = self.requests[0]
        assert sent.headers["Content-Type"] == "application/pdf"
        assert sent.headers["x-upsert"] == "true"

    def test_public_url_points_at_public_endpoint(self) -> None:
        url = self.make(public=True).public_url(KEY)
        assert url == f"https://proj.supabase.co/storage/v1/object/public/bucket/{KEY}"

    async def test_server_error_raises_provider_error(self) -> None:
        http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
        store = SupabaseObjectStore(
            http, project_url="https://p", service_role_key="k", bucket="b", public=False
        )
        with pytest.raises(ProviderError):
            await store.get(KEY)
