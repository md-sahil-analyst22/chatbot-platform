"""Google Gemini generateContent adapter (implements CompletionClient).

Constructed per API key (platform key today, the tenant's own key in Phase 8). Model and
temperature come with each request from the bot's configuration.
"""

from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from saathi.modules.conversation.adapters import completion_registry
from saathi.modules.conversation.ports.llm import ChatMessage, LLMResponse
from saathi.platform.errors import ProviderError, ProviderTimeoutError

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Gemini calls the assistant "model".
_ROLES = {"user": "user", "assistant": "model"}


class GeminiSettings(BaseSettings):
    """Platform-level defaults. GEMINI_API_KEY is the PLATFORM key, not a tenant key."""

    model_config = SettingsConfigDict(env_prefix="GEMINI_", env_file=".env", extra="ignore")

    api_key: SecretStr | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 20.0


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


@completion_registry.register("gemini")
def create_gemini_completion_client(
    http: httpx.AsyncClient, api_key: str
) -> GeminiCompletionClient:
    s = GeminiSettings()
    return GeminiCompletionClient(
        http, api_key=api_key, base_url=s.base_url, timeout_s=s.timeout_seconds
    )
