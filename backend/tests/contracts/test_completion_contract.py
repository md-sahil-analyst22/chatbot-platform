# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every AI language model adapter must follow, including timeouts and
#                errors.
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# json — reads and writes JSON text.
import json

# From typing — type-hint helpers: Any = any type.
from typing import Any

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.providers — fake vendor adapters: FakeCompletionClient = fake AI model; Mode
#   = which failure a fake should simulate.
from tests.fakes.providers import FakeCompletionClient, Mode

# From saathi.modules.conversation.adapters.llm.anthropic_llm — the Anthropic Claude adapter:
#   AnthropicCompletionClient = the Claude client.
from saathi.modules.conversation.adapters.llm.anthropic_llm import AnthropicCompletionClient

# From saathi.modules.conversation.adapters.llm.gemini_llm — the Google Gemini adapter:
#   GeminiCompletionClient = the Gemini client.
from saathi.modules.conversation.adapters.llm.gemini_llm import GeminiCompletionClient

# From saathi.modules.conversation.ports.llm — AI language-model contracts: ChatMessage = one
#   chat message; CompletionClient = contract: messages in, reply out.
from saathi.modules.conversation.ports.llm import ChatMessage, CompletionClient

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ProviderTimeoutError = a vendor was too slow.
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


class TestGeminiCompletionClient(CompletionClientContract):
    sent: dict[str, Any]
    url: str

    def make(self, mode: Mode = "ok") -> CompletionClient:
        def handler(request: httpx.Request) -> httpx.Response:
            if mode == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if mode == "error":
                return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
            self.url = str(request.url)
            self.sent = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "candidates": [{"content": {"role": "model", "parts": [{"text": "Dam 500."}]}}],
                    "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4},
                },
            )

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return GeminiCompletionClient(http, api_key="t")

    async def test_sends_bot_model_temperature_and_system(self) -> None:
        msgs = [*MSGS, ChatMessage(role="assistant", content="500"), *MSGS]
        await self.make().complete(**{**ARGS, "messages": msgs})  # type: ignore[arg-type]
        assert self.url.endswith("/models/m-1:generateContent")
        assert self.sent["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 50}
        assert self.sent["systemInstruction"] == {"parts": [{"text": "s"}]}
        assert [c["role"] for c in self.sent["contents"]] == ["user", "model", "user"]

    async def test_blocked_prompt_raises_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(ProviderError):
            await GeminiCompletionClient(http, api_key="t").complete(**ARGS)  # type: ignore[arg-type]
