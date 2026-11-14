import json

import httpx
import pytest
from tests.fakes.providers import FakeCompletionClient, Mode

from saathi.modules.conversation.adapters.llm.anthropic_llm import AnthropicCompletionClient
from saathi.modules.conversation.ports.llm import ChatMessage, CompletionClient
from saathi.platform.errors import ProviderError, ProviderTimeoutError

MSGS = [ChatMessage(role="user", content="ar price koto?")]
ARGS = {"system": "s", "messages": MSGS, "model": "m-1", "temperature": 0.2, "max_tokens": 50}


class CompletionClientContract:
    def make(self, mode: Mode = "ok") -> CompletionClient:
        raise NotImplementedError

    async def test_returns_text_usage_and_requested_model(self) -> None:
        r = await self.make().complete(**ARGS)  # type: ignore[arg-type]
        assert r.text
        assert r.tokens_in >= 0 and r.tokens_out >= 0
        assert r.model == "m-1"

    async def test_failure_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError):
            await self.make("error").complete(**ARGS)  # type: ignore[arg-type]

    async def test_timeout_raises_provider_timeout(self) -> None:
        with pytest.raises(ProviderTimeoutError):
            await self.make("timeout").complete(**ARGS)  # type: ignore[arg-type]


class TestFakeCompletionClient(CompletionClientContract):
    def make(self, mode: Mode = "ok") -> CompletionClient:
        return FakeCompletionClient(mode)


class TestAnthropicCompletionClient(CompletionClientContract):
    sent: dict[str, object]

    def make(self, mode: Mode = "ok") -> CompletionClient:
        def handler(request: httpx.Request) -> httpx.Response:
            if mode == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if mode == "error":
                return httpx.Response(529, json={"type": "error"})
            self.sent = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "Dam 500 taka."}],
                    "usage": {"input_tokens": 12, "output_tokens": 5},
                },
            )

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return AnthropicCompletionClient(http, api_key="t")

    async def test_sends_bot_model_and_temperature(self) -> None:
        await self.make().complete(**ARGS)  # type: ignore[arg-type]
        assert self.sent["model"] == "m-1"
        assert self.sent["temperature"] == 0.2
        assert self.sent["max_tokens"] == 50
