# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Talks to Google Gemini to generate chat replies (the primary AI vendor, ADR-0006).
# Safety: Timeouts and vendor errors become typed errors; the API key is sent in a header, never
#         in the URL.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Google Gemini generateContent adapter (implements CompletionClient).

Constructed per API key (platform key today, the tenant's own key in Phase 8). Model and
temperature come with each request from the bot's configuration.
"""

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# From typing — type-hint helpers: Any = any type.
from typing import Any

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

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Gemini calls the assistant "model".
_ROLES = {"user": "user", "assistant": "model"}


# GEMINI_* settings from .env.
class GeminiSettings(BaseSettings):
    """Platform-level defaults. GEMINI_API_KEY is the PLATFORM key, not a tenant key."""

    model_config = SettingsConfigDict(env_prefix="GEMINI_", env_file=".env", extra="ignore")

    api_key: SecretStr | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 20.0


# The Gemini chat client.
class GeminiCompletionClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 20.0,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._headers = {"x-goog-api-key": api_key}
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
                f"{self._base_url}/models/{model}:generateContent",
                headers=self._headers,
                timeout=self._timeout,
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [
                        {"role": _ROLES[m.role], "parts": [{"text": m.content}]} for m in messages
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                    },
                },
            )
            r.raise_for_status()
            body: dict[str, Any] = r.json()
            candidates = body.get("candidates") or []
            if not candidates:
                # Blocked prompt (promptFeedback.blockReason) or empty answer.
                raise ProviderError("LLM returned no answer")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            usage = body.get("usageMetadata", {})
            return LLMResponse(
                text=text,
                model=model,
                tokens_in=int(usage.get("promptTokenCount", 0)),
                tokens_out=int(usage.get("candidatesTokenCount", 0)),
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("LLM timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ProviderError("LLM request failed") from exc


# Register under the name 'gemini'.
@completion_registry.register("gemini")
def create_gemini_completion_client(
    http: httpx.AsyncClient, api_key: str
) -> GeminiCompletionClient:
    s = GeminiSettings()
    return GeminiCompletionClient(
        http, api_key=api_key, base_url=s.base_url, timeout_s=s.timeout_seconds
    )
