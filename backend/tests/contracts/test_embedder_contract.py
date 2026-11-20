# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every embedder must follow (right count and size of vectors, errors).
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# json — reads and writes JSON text.
import json

# math — maths functions.
import math

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.providers — fake vendor adapters: FakeEmbedder = fake embedder; Mode = which
#   failure a fake should simulate.
from tests.fakes.providers import FakeEmbedder, Mode

# From saathi.modules.knowledge.adapters.embeddings.gemini_embedder — the Gemini embedder:
#   MAX_BATCH = most texts per Gemini call; GeminiEmbedder = the Gemini embedder.
from saathi.modules.knowledge.adapters.embeddings.gemini_embedder import MAX_BATCH, GeminiEmbedder

# From saathi.modules.knowledge.adapters.embeddings.openai_embedder — the OpenAI embedder:
#   OpenAIEmbedder = the OpenAI embedder.
from saathi.modules.knowledge.adapters.embeddings.openai_embedder import OpenAIEmbedder

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   Embedder = contract: text -> vectors.
from saathi.modules.knowledge.ports.providers import Embedder

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ProviderTimeoutError = a vendor was too slow.
from saathi.platform.errors import ProviderError, ProviderTimeoutError


# The rules EVERY embedder must follow (fake, OpenAI, Gemini).
class EmbedderContract:
    # Each concrete test class below says which implementation to test by overriding make();
    #   `mode` asks it to work, fail or time out.
    def make(self, mode: Mode = "ok") -> Embedder:
        # The base class itself has no implementation.
        raise NotImplementedError

    # One vector per text.
    async def test_one_vector_per_text_in_order(self) -> None:
        # Embed three texts.
        out = await self.make().embed(["a", "b", "c"])
        # Three vectors back.
        assert len(out) == 3

    # All vectors have the same, non-zero length.
    async def test_vectors_have_one_dimension(self) -> None:
        # Embed two texts.
        out = await self.make().embed(["a", "b"])
        # One distinct length, and it's above zero.
        assert len({len(v) for v in out}) == 1 and len(out[0]) > 0

    # No texts -> no vectors.
    async def test_empty_input_returns_empty(self) -> None:
        # Must be an empty list.
        assert await self.make().embed([]) == []

    # A vendor failure becomes ProviderError.
    async def test_failure_raises_provider_error(self) -> None:
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            # embed in 'error' mode.
            await self.make("error").embed(["a"])

    # A vendor timeout becomes ProviderTimeoutError.
    async def test_timeout_raises_provider_timeout(self) -> None:
        # Expect ProviderTimeoutError from the next line:
        with pytest.raises(ProviderTimeoutError):
            # embed in 'timeout' mode.
            await self.make("timeout").embed(["a"])


# Run the rules against the fake embedder.
class TestFakeEmbedder(EmbedderContract):
    # Which implementation:
    def make(self, mode: Mode = "ok") -> Embedder:
        # the fake.
        return FakeEmbedder(mode)


# Run the rules against the real OpenAI adapter, with a fake OpenAI server.
class TestOpenAIEmbedder(EmbedderContract):
    # Which implementation:
    def make(self, mode: Mode = "ok") -> Embedder:
        # A fake OpenAI server that answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # in timeout mode...
            if mode == "timeout":
                # ...raise a timeout;
                raise httpx.ReadTimeout("timeout", request=request)
            # in error mode...
            if mode == "error":
                # ...answer with a server error;
                return httpx.Response(500, json={"error": "boom"})
            # otherwise read the texts sent,
            texts = json.loads(request.content)["input"]
            # reversed on purpose: the adapter must restore order by index
            data = [{"index": i, "embedding": [0.1 * (i + 1)] * 4} for i in range(len(texts))]
            # and answer with the results in REVERSED order (the adapter must re-sort them).
            return httpx.Response(200, json={"data": list(reversed(data))})

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real OpenAI adapter using it.
        return OpenAIEmbedder(http, api_key="test", model_name="test-model")

    # OpenAI-specific: results are put back in the original order.
    async def test_restores_order_by_index(self) -> None:
        # Embed two texts.
        out = await self.make().embed(["a", "b"])
        # The first vector belongs to the first text.
        assert out[0][0] < out[1][0]


# Run the rules against the real Gemini adapter, with a fake Gemini server.
class TestGeminiEmbedder(EmbedderContract):
    # Vector size used in these tests.
    DIM = 4
    # How many texts arrived in each call (filled by the fake server).
    batch_sizes: list[int]

    # Which implementation; `dim_returned` lets a test make the server send the wrong size.
    def make(self, mode: Mode = "ok", dim_returned: int | None = None) -> Embedder:
        # Reset the batch log.
        self.batch_sizes = []

        # A fake Gemini server that answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # in timeout mode...
            if mode == "timeout":
                # ...raise a timeout;
                raise httpx.ReadTimeout("timeout", request=request)
            # in error mode...
            if mode == "error":
                # ...answer with a server error;
                return httpx.Response(500, json={"error": "boom"})
            # otherwise read the requests sent,
            reqs = json.loads(request.content)["requests"]
            # check that each asked for the right vector size,
            assert all(r["outputDimensionality"] == self.DIM for r in reqs)
            # record the batch size,
            self.batch_sizes.append(len(reqs))
            # pick the size to send back,
            size = dim_returned or self.DIM
            # and answer 200 with one vector of 3.0s per text.
            return httpx.Response(
                200, json={"embeddings": [{"values": [3.0] * size} for _ in reqs]}
            )

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real Gemini adapter using it.
        return GeminiEmbedder(http, api_key="test", model_name="m", dimensions=self.DIM)

    # Gemini-specific: every vector is scaled to length 1.
    async def test_vectors_are_l2_normalised(self) -> None:
        # Embed two texts.
        out = await self.make().embed(["a", "b"])
        # Each vector's length is 1.
        assert all(math.isclose(math.sqrt(sum(x * x for x in v)), 1.0) for v in out)

    # Gemini-specific: more than 100 texts are split into batches.
    async def test_splits_large_inputs_into_batches(self) -> None:
        # An embedder.
        embedder = self.make()
        # Embed 105 texts.
        out = await embedder.embed(["t"] * (MAX_BATCH + 5))
        # 105 vectors back...
        assert len(out) == MAX_BATCH + 5
        # ...sent as one batch of 100 and one of 5.
        assert self.batch_sizes == [MAX_BATCH, 5]

    # Gemini-specific: a wrong vector size is caught.
    async def test_wrong_dimension_raises_provider_error(self) -> None:
        # Expect a ProviderError mentioning 'dimension' from the next line:
        with pytest.raises(ProviderError, match="dimension"):
            # the server sends one number too many.
            await self.make(dim_returned=self.DIM + 1).embed(["a"])
