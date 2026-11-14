import json
import math

import httpx
import pytest
from tests.fakes.providers import FakeEmbedder, Mode

from saathi.modules.knowledge.adapters.embeddings.gemini_embedder import MAX_BATCH, GeminiEmbedder
from saathi.modules.knowledge.adapters.embeddings.openai_embedder import OpenAIEmbedder
from saathi.modules.knowledge.ports.providers import Embedder
from saathi.platform.errors import ProviderError, ProviderTimeoutError


class EmbedderContract:
    def make(self, mode: Mode = "ok") -> Embedder:
        raise NotImplementedError

    async def test_one_vector_per_text_in_order(self) -> None:
        out = await self.make().embed(["a", "b", "c"])
        assert len(out) == 3

    async def test_vectors_have_one_dimension(self) -> None:
        out = await self.make().embed(["a", "b"])
        assert len({len(v) for v in out}) == 1 and len(out[0]) > 0

    async def test_empty_input_returns_empty(self) -> None:
        assert await self.make().embed([]) == []

    async def test_failure_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError):
            await self.make("error").embed(["a"])

    async def test_timeout_raises_provider_timeout(self) -> None:
        with pytest.raises(ProviderTimeoutError):
            await self.make("timeout").embed(["a"])


class TestFakeEmbedder(EmbedderContract):
    def make(self, mode: Mode = "ok") -> Embedder:
        return FakeEmbedder(mode)


class TestOpenAIEmbedder(EmbedderContract):
    def make(self, mode: Mode = "ok") -> Embedder:
        def handler(request: httpx.Request) -> httpx.Response:
            if mode == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if mode == "error":
                return httpx.Response(500, json={"error": "boom"})
            texts = json.loads(request.content)["input"]
            # reversed on purpose: the adapter must restore order by index
            data = [{"index": i, "embedding": [0.1 * (i + 1)] * 4} for i in range(len(texts))]
            return httpx.Response(200, json={"data": list(reversed(data))})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return OpenAIEmbedder(http, api_key="test", model_name="test-model")

    async def test_restores_order_by_index(self) -> None:
        out = await self.make().embed(["a", "b"])
        assert out[0][0] < out[1][0]


class TestGeminiEmbedder(EmbedderContract):
    DIM = 4
    batch_sizes: list[int]

    def make(self, mode: Mode = "ok", dim_returned: int | None = None) -> Embedder:
        self.batch_sizes = []

        def handler(request: httpx.Request) -> httpx.Response:
            if mode == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if mode == "error":
                return httpx.Response(500, json={"error": "boom"})
            reqs = json.loads(request.content)["requests"]
            assert all(r["outputDimensionality"] == self.DIM for r in reqs)
            self.batch_sizes.append(len(reqs))
            size = dim_returned or self.DIM
            return httpx.Response(
                200, json={"embeddings": [{"values": [3.0] * size} for _ in reqs]}
            )

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return GeminiEmbedder(http, api_key="test", model_name="m", dimensions=self.DIM)

    async def test_vectors_are_l2_normalised(self) -> None:
        out = await self.make().embed(["a", "b"])
        assert all(math.isclose(math.sqrt(sum(x * x for x in v)), 1.0) for v in out)

    async def test_splits_large_inputs_into_batches(self) -> None:
        embedder = self.make()
        out = await embedder.embed(["t"] * (MAX_BATCH + 5))
        assert len(out) == MAX_BATCH + 5
        assert self.batch_sizes == [MAX_BATCH, 5]

    async def test_wrong_dimension_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError, match="dimension"):
            await self.make(dim_returned=self.DIM + 1).embed(["a"])
