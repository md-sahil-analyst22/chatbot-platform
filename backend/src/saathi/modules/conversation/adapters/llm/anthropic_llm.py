# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Talks to Anthropic Claude to generate chat replies (an alternative vendor, chosen per
#       bot via the model catalog).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Anthropic Messages API adapter (implements CompletionClient).

Constructed per API key (platform key today, the tenant's own key in Phase 8). Model and
temperature come with each request from the bot's configuration.
"""

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# httpx — the HTTP client we use to call other web services.
import httpx

# From pydantic — checks data against declared types and rules: SecretStr = text that hides
#   itself when printed or logged.
from pydantic import SecretStr

# From pydantic_settings — reads settings from environment variables and .env: BaseSettings =
#   parent class for a group of settings; SettingsConfigDict = where settings are read from (.env,
#   prefix).
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.modules.conversation.adapters — the AI language-model registry:
#   completion_registry = the AI language-model registry.
from saathi.modules.conversation.adapters import completion_registry

# From saathi.modules.conversation.ports.llm — AI language-model contracts: ChatMessage = one
#   chat message; LLMResponse = the model's reply and token counts.
from saathi.modules.conversation.ports.llm import ChatMessage, LLMResponse

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ProviderTimeoutError = a vendor was too slow.
from saathi.platform.errors import ProviderError, ProviderTimeoutError

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"


# ANTHROPIC_* settings from .env.
class AnthropicSettings(BaseSettings):
    """Platform-level defaults. ANTHROPIC_API_KEY is the PLATFORM key, not a tenant key."""

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", env_file=".env", extra="ignore")

    api_key: SecretStr | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 20.0


# The Claude chat client.
class AnthropicCompletionClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 20.0,
    ) -> None:
        self._http = http
        self._url = f"{base_url.rstrip('/')}/messages"
        self._headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        self._timeout = timeout_s

    # Send the conversation, return the reply and token counts.
    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        try:
            r = await self._http.post(
                self._url,
                headers=self._headers,
                timeout=self._timeout,
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system,
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                },
            )
            r.raise_for_status()
            body = r.json()
            text = "".join(
                b.get("text", "") for b in body.get("content", []) if b.get("type") == "text"
            )
            usage = body.get("usage", {})
            return LLMResponse(
                text=text,
                model=model,
                tokens_in=int(usage.get("input_tokens", 0)),
                tokens_out=int(usage.get("output_tokens", 0)),
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("LLM timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("LLM request failed") from exc


# Register under the name 'anthropic'.
@completion_registry.register("anthropic")
def create_anthropic_completion_client(
    http: httpx.AsyncClient, api_key: str
) -> AnthropicCompletionClient:
    s = AnthropicSettings()
    return AnthropicCompletionClient(
        http, api_key=api_key, base_url=s.base_url, timeout_s=s.timeout_seconds
    )
