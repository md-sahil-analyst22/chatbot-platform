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

# Google's Gemini API address.
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Gemini calls the assistant "model".
_ROLES = {"user": "user", "assistant": "model"}


# GEMINI_* settings from .env.
class GeminiSettings(BaseSettings):
    """Platform-level defaults. GEMINI_API_KEY is the PLATFORM key, not a tenant key."""

    # Read GEMINI_* variables from .env and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="GEMINI_", env_file=".env", extra="ignore")

    # 🔒 GEMINI_API_KEY (hidden when printed).
    api_key: SecretStr | None = None
    # GEMINI_BASE_URL (normally the default).
    base_url: str = DEFAULT_BASE_URL
    # GEMINI_TIMEOUT_SECONDS: give up after 20 s by default.
    timeout_seconds: float = 20.0


# The Gemini chat client.
class GeminiCompletionClient:
    # Created per bot by the LLM resolver with:
    def __init__(
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        # the API address,
        base_url: str = DEFAULT_BASE_URL,
        # and the time limit.
        timeout_s: float = 20.0,
    ) -> None:
        # Remember the HTTP client.
        self._http = http
        # The API address without a trailing '/'.
        self._base_url = base_url.rstrip("/")
        # 🔒 The key travels in a header, never in the URL.
        self._headers = {"x-goog-api-key": api_key}
        # Remember the time limit.
        self._timeout = timeout_s

    # Send the conversation, return the reply and token counts.
    async def complete(
        # Inputs (by name, thanks to the '*'):
        self,
        *,
        system: str,
        # the conversation so far,
        messages: Sequence[ChatMessage],
        # the Gemini model id,
        model: str,
        # creativity,
        temperature: float,
        # the longest reply allowed.
        max_tokens: int,
    ) -> LLMResponse:
        # Try the call:
        try:
            # POST to Gemini
            r = await self._http.post(
                # at <base>/models/<model>:generateContent,
                f"{self._base_url}/models/{model}:generateContent",
                # with the key header,
                headers=self._headers,
                # within the time limit,
                timeout=self._timeout,
                # sending JSON:
                json={
                    # our system prompt,
                    "systemInstruction": {"parts": [{"text": system}]},
                    # the conversation, each message with Gemini's role name,
                    "contents": [
                        {"role": _ROLES[m.role], "parts": [{"text": m.content}]} for m in messages
                    ],
                    # and the generation settings:
                    "generationConfig": {
                        # creativity,
                        "temperature": temperature,
                        # reply length limit.
                        "maxOutputTokens": max_tokens,
                    },
                },
            )
            # An error status counts as a failure.
            r.raise_for_status()
            # Read the JSON answer.
            body: dict[str, Any] = r.json()
            # Gemini's possible answers ('candidates'), or an empty list.
            candidates = body.get("candidates") or []
            # No answer at all:
            if not candidates:
                # Blocked prompt (promptFeedback.blockReason) or empty answer.
                raise ProviderError("LLM returned no answer")
            # The pieces of the first answer.
            parts = candidates[0].get("content", {}).get("parts", [])
            # Join their text into one reply.
            text = "".join(p.get("text", "") for p in parts)
            # Token counts, if Gemini sent them.
            usage = body.get("usageMetadata", {})
            # Return:
            return LLMResponse(
                # the reply,
                text=text,
                # the model,
                model=model,
                # tokens sent,
                tokens_in=int(usage.get("promptTokenCount", 0)),
                # tokens received.
                tokens_out=int(usage.get("candidatesTokenCount", 0)),
            )
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("LLM timed out") from exc
        # Network problem or unexpected answer shape:
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
            # vendor error (the message never includes the key or the prompt).
            raise ProviderError("LLM request failed") from exc


# Register under the name 'gemini'.
@completion_registry.register("gemini")
# The factory the registry calls with the HTTP client and the key to use.
def create_gemini_completion_client(
    http: httpx.AsyncClient, api_key: str
) -> GeminiCompletionClient:
    # Read the GEMINI_* settings (address and time limit; the key is passed in).
    s = GeminiSettings()
    # Build the client.
    return GeminiCompletionClient(
        http, api_key=api_key, base_url=s.base_url, timeout_s=s.timeout_seconds
    )
