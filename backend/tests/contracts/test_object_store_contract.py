# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every file store must follow (put/get/delete, safe paths).
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.providers — fake vendor adapters: InMemoryObjectStore = file storage in a
#   dict.
from tests.fakes.providers import InMemoryObjectStore

# From saathi.platform.errors — our error types: NotFoundError = 404 not found; ProviderError =
#   a vendor failed; ValidationError = 422 invalid input.
from saathi.platform.errors import NotFoundError, ProviderError, ValidationError

# From saathi.platform.storage — file storage contract and registry: ObjectStore = the file
#   storage contract.
from saathi.platform.storage import ObjectStore

# From saathi.platform.storage.supabase_store — Supabase file storage: SupabaseObjectStore =
#   Supabase file storage.
from saathi.platform.storage.supabase_store import SupabaseObjectStore

# A valid file path: starts with t/<tenant>/.
KEY = "t/tenant-1/docs/price-list.pdf"
# 🔒 Invalid paths: no tenant prefix, nothing after the tenant, '..' climbing out, a leading
#   '/', a space.
BAD_KEYS = ["docs/a.pdf", "t/tenant-1", "t/tenant-1/../tenant-2/a.pdf", "/t/x/a", "t/x/a b.pdf"]


# The rules EVERY file store must follow (in-memory fake and Supabase).
class ObjectStoreContract:
    # Each concrete test class below says which implementation to test; `public` picks the
    #   bucket type.
    def make(self, *, public: bool = False) -> ObjectStore:
        # The base class itself has no implementation.
        raise NotImplementedError

    # Saving then reading gives the same bytes.
    async def test_put_then_get_round_trips(self) -> None:
        # A store.
        store = self.make()
        # Save a tiny 'PDF'.
        await store.put(KEY, b"%PDF-1.7", "application/pdf")
        # Read it back: identical.
        assert await store.get(KEY) == b"%PDF-1.7"

    # Reading a missing file gives NotFoundError.
    async def test_get_missing_raises_not_found(self) -> None:
        # Expect NotFoundError from the next line:
        with pytest.raises(NotFoundError):
            # read a path that was never saved.
            await self.make().get("t/tenant-1/docs/missing.pdf")

    # Deleting twice is fine.
    async def test_delete_is_idempotent(self) -> None:
        # A store.
        store = self.make()
        # Save a file.
        await store.put(KEY, b"x", "text/plain")
        # Delete it.
        await store.delete(KEY)
        # Delete it again (no error).
        await store.delete(KEY)
        # Expect NotFoundError from the next line:
        with pytest.raises(NotFoundError):
            # it's really gone.
            await store.get(KEY)

    # Run once per bad path.
    @pytest.mark.parametrize("key", BAD_KEYS)
    # 🔒 Every bad path is refused before anything is sent.
    async def test_rejects_keys_without_tenant_prefix_or_with_traversal(self, key: str) -> None:
        # Expect ValidationError from the next line:
        with pytest.raises(ValidationError):
            # try to save at the bad path.
            await self.make().put(key, b"x", "text/plain")

    # Private stores have no public address.
    def test_private_store_has_no_public_url(self) -> None:
        # Must be None.
        assert self.make(public=False).public_url(KEY) is None

    # Public stores give a public address ending with the path.
    def test_public_store_has_public_url(self) -> None:
        # Ask for it.
        url = self.make(public=True).public_url(KEY)
        # It exists and ends with the path.
        assert url is not None and url.endswith(KEY)


# Run the rules against the in-memory fake.
class TestInMemoryObjectStore(ObjectStoreContract):
    # Which implementation:
    def make(self, *, public: bool = False) -> ObjectStore:
        # the fake.
        return InMemoryObjectStore(public=public)


# Run the rules against the real Supabase adapter, with a fake Supabase server.
class TestSupabaseObjectStore(ObjectStoreContract):
    """Simulates the Supabase Storage REST API in memory."""

    # Every request the adapter sent (filled by the fake server).
    requests: list[httpx.Request]

    # Which implementation:
    def make(self, *, public: bool = False) -> ObjectStore:
        # The fake server's stored files.
        objects: dict[str, bytes] = {}
        # The path prefix every request must use.
        prefix = "/storage/v1/object/bucket/"
        # Reset the request log.
        self.requests = []

        # The fake server answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # record it,
            self.requests.append(request)
            # 🔒 check the secret key was sent,
            assert request.headers["Authorization"] == "Bearer service-key"
            # take the path,
            path = request.url.path
            # check it's in our bucket,
            assert path.startswith(prefix)
            # and work out the file path.
            key = path.removeprefix(prefix)
            # Upload:
            if request.method == "POST":
                # store the bytes,
                objects[key] = request.read()
                # answer 200.
                return httpx.Response(200, json={"Key": f"bucket/{key}"})
            # Unknown file:
            if key not in objects:
                # Supabase reports missing objects as 400 + statusCode "404"
                return httpx.Response(400, json={"statusCode": "404", "error": "not_found"})
            # Download:
            if request.method == "GET":
                # answer with the bytes.
                return httpx.Response(200, content=objects[key])
            # Otherwise it's a delete: remove the file,
            del objects[key]
            # answer 200.
            return httpx.Response(200, json={"message": "deleted"})

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real Supabase adapter with:
        return SupabaseObjectStore(
            # that client,
            http,
            # a test project address,
            project_url="https://proj.supabase.co",
            # a test secret key,
            service_role_key="service-key",
            # a test bucket,
            bucket="bucket",
            # public or private.
            public=public,
        )

    # Supabase-specific: uploads send the file type and ask to overwrite.
    async def test_upload_sends_content_type_and_upserts(self) -> None:
        # Upload a file.
        await self.make().put(KEY, b"x", "application/pdf")
        # The request that was sent.
        sent = self.requests[0]
        # It carried the file type...
        assert sent.headers["Content-Type"] == "application/pdf"
        # ...and x-upsert: true.
        assert sent.headers["x-upsert"] == "true"

    # Supabase-specific: the public address uses Supabase's /public/ path.
    def test_public_url_points_at_public_endpoint(self) -> None:
        # Ask for it.
        url = self.make(public=True).public_url(KEY)
        # Exact address.
        assert url == f"https://proj.supabase.co/storage/v1/object/public/bucket/{KEY}"

    # Supabase-specific: a server error becomes ProviderError.
    async def test_server_error_raises_provider_error(self) -> None:
        # An HTTP client whose every request gets 500.
        http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
        # A Supabase store using it.
        store = SupabaseObjectStore(
            http, project_url="https://p", service_role_key="k", bucket="b", public=False
        )
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            # read a file.
            await store.get(KEY)
