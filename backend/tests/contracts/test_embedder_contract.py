import json

import httpx
import pytest
from tests.fakes.providers import FakeEmbedder, Mode

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
