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

# A one-message test conversation (a Banglish price question).
MSGS = [ChatMessage(role="user", content="ar price koto?")]
# The arguments every test sends: system prompt, messages, model, temperature, length limit.
ARGS = {"system": "s", "messages": MSGS, "model": "m-1", "temperature": 0.2, "max_tokens": 50}


# The rules EVERY AI chat client must follow (fake, Anthropic, Gemini).
class CompletionClientContract:
    # Each concrete test class below says which implementation to test by overriding make();
    #   `mode` asks it to work, fail or time out.
    def make(self, mode: Mode = "ok") -> CompletionClient:
        # The base class itself has no implementation.
        raise NotImplementedError

    # A reply has text, token counts, and names the model we asked for.
    async def test_returns_text_usage_and_requested_model(self) -> None:
        r = await self.make().complete(**ARGS)  # type: ignore[arg-type]
        # Some text came back.
        assert r.text
        # Token counts aren't negative.
        assert r.tokens_in >= 0 and r.tokens_out >= 0
        # It reports the requested model.
        assert r.model == "m-1"

    # A vendor failure becomes ProviderError.
    async def test_failure_raises_provider_error(self) -> None:
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            await self.make("error").complete(**ARGS)  # type: ignore[arg-type]

    # A vendor timeout becomes ProviderTimeoutError.
    async def test_timeout_raises_provider_timeout(self) -> None:
        # Expect ProviderTimeoutError from the next line:
        with pytest.raises(ProviderTimeoutError):
            await self.make("timeout").complete(**ARGS)  # type: ignore[arg-type]


# Run the rules against the fake client.
class TestFakeCompletionClient(CompletionClientContract):
    # Which implementation:
    def make(self, mode: Mode = "ok") -> CompletionClient:
        # the fake.
        return FakeCompletionClient(mode)


# Run the rules against the real Anthropic adapter, with a fake Anthropic server.
class TestAnthropicCompletionClient(CompletionClientContract):
    # What the adapter sent (recorded by the fake server).
    sent: dict[str, object]

    # Which implementation:
    def make(self, mode: Mode = "ok") -> CompletionClient:
        # A fake Anthropic server that answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # in timeout mode...
            if mode == "timeout":
                # ...raise a timeout;
                raise httpx.ReadTimeout("timeout", request=request)
            # in error mode...
            if mode == "error":
                # ...answer 529 (overloaded);
                return httpx.Response(529, json={"type": "error"})
            # otherwise record what was sent,
            self.sent = json.loads(request.content)
            # and answer 200 with:
            return httpx.Response(
                # (status)
                200,
                # this body:
                json={
                    # one text block,
                    "content": [{"type": "text", "text": "Dam 500 taka."}],
                    # token counts.
                    "usage": {"input_tokens": 12, "output_tokens": 5},
                },
            )

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real Anthropic adapter using it.
        return AnthropicCompletionClient(http, api_key="t")

    # Anthropic-specific: the bot's model and settings are sent.
    async def test_sends_bot_model_and_temperature(self) -> None:
        # Make a call.
        await self.make().complete(**ARGS)  # type: ignore[arg-type]
        # The model,
        assert self.sent["model"] == "m-1"
        # the temperature,
        assert self.sent["temperature"] == 0.2
        # and the length limit were sent.
        assert self.sent["max_tokens"] == 50


# Run the rules against the real Gemini adapter, with a fake Gemini server.
class TestGeminiCompletionClient(CompletionClientContract):
    # What the adapter sent.
    sent: dict[str, Any]
    # Which address it called.
    url: str

    # Which implementation:
    def make(self, mode: Mode = "ok") -> CompletionClient:
        # A fake Gemini server that answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # in timeout mode...
            if mode == "timeout":
                # ...raise a timeout;
                raise httpx.ReadTimeout("timeout", request=request)
            # in error mode...
            if mode == "error":
                # ...answer 503;
                return httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
            # otherwise record the address,
            self.url = str(request.url)
            # record what was sent,
            self.sent = json.loads(request.content)
            # and answer 200 with:
            return httpx.Response(
                # (status)
                200,
                # this body:
                json={
                    # one answer,
                    "candidates": [{"content": {"role": "model", "parts": [{"text": "Dam 500."}]}}],
                    # token counts.
                    "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4},
                },
            )

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real Gemini adapter using it.
        return GeminiCompletionClient(http, api_key="t")

    # Gemini-specific: the model, settings, system prompt and roles are sent correctly.
    async def test_sends_bot_model_temperature_and_system(self) -> None:
        # A three-message conversation: user, assistant, user.
        msgs = [*MSGS, ChatMessage(role="assistant", content="500"), *MSGS]
        await self.make().complete(**{**ARGS, "messages": msgs})  # type: ignore[arg-type]
        # The model is in the address.
        assert self.url.endswith("/models/m-1:generateContent")
        # Temperature and length limit are sent.
        assert self.sent["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 50}
        # The system prompt is sent separately.
        assert self.sent["systemInstruction"] == {"parts": [{"text": "s"}]}
        # 'assistant' is translated to Gemini's 'model'.
        assert [c["role"] for c in self.sent["contents"]] == ["user", "model", "user"]

    # Gemini-specific: a blocked prompt (no answer) becomes ProviderError.
    async def test_blocked_prompt_raises_provider_error(self) -> None:
        # A fake server...
        def handler(request: httpx.Request) -> httpx.Response:
            # ...that always says 'blocked for safety' with no answer.
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})

        # An HTTP client wired to it.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            await GeminiCompletionClient(http, api_key="t").complete(**ARGS)  # type: ignore[arg-type]
