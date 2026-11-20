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

# Anthropic's API address.
DEFAULT_BASE_URL = "https://api.anthropic.com/v1"


# ANTHROPIC_* settings from .env.
class AnthropicSettings(BaseSettings):
    """Platform-level defaults. ANTHROPIC_API_KEY is the PLATFORM key, not a tenant key."""

    # Read ANTHROPIC_* variables from .env and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", env_file=".env", extra="ignore")

    # 🔒 ANTHROPIC_API_KEY (hidden when printed).
    api_key: SecretStr | None = None
    # ANTHROPIC_BASE_URL (normally the default).
    base_url: str = DEFAULT_BASE_URL
    # ANTHROPIC_TIMEOUT_SECONDS: give up after 20 s by default.
    timeout_seconds: float = 20.0


# The Claude chat client.
class AnthropicCompletionClient:
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
        # The Messages API address.
        self._url = f"{base_url.rstrip('/')}/messages"
        # 🔒 The key travels in a header, plus the API version Anthropic requires.
        self._headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
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
        # the Claude model id,
        model: str,
        # creativity,
        temperature: float,
        # the longest reply allowed.
        max_tokens: int,
    ) -> LLMResponse:
        # Try the call:
        try:
            # POST to Anthropic
            r = await self._http.post(
                # at the Messages address,
                self._url,
                # with the key headers,
                headers=self._headers,
                # within the time limit,
                timeout=self._timeout,
                # sending JSON:
                json={
                    # the model,
                    "model": model,
                    # the reply length limit,
                    "max_tokens": max_tokens,
                    # creativity,
                    "temperature": temperature,
                    # our system prompt,
                    "system": system,
                    # the conversation.
                    "messages": [{"role": m.role, "content": m.content} for m in messages],
                },
            )
            # An error status counts as a failure.
            r.raise_for_status()
            # Read the JSON answer.
            body = r.json()
            # Join the text blocks of the answer into one reply.
            text = "".join(
                b.get("text", "") for b in body.get("content", []) if b.get("type") == "text"
            )
            # Token counts, if sent.
            usage = body.get("usage", {})
            # Return:
            return LLMResponse(
                # the reply,
                text=text,
                # the model,
                model=model,
                # tokens sent,
                tokens_in=int(usage.get("input_tokens", 0)),
                # tokens received.
                tokens_out=int(usage.get("output_tokens", 0)),
            )
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("LLM timed out") from exc
        # Network problem or unexpected answer:
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            # vendor error.
            raise ProviderError("LLM request failed") from exc


# Register under the name 'anthropic'.
@completion_registry.register("anthropic")
# The factory the registry calls with the HTTP client and the key to use.
def create_anthropic_completion_client(
    http: httpx.AsyncClient, api_key: str
) -> AnthropicCompletionClient:
    # Read the ANTHROPIC_* settings (address and time limit).
    s = AnthropicSettings()
    # Build the client.
    return AnthropicCompletionClient(
        http, api_key=api_key, base_url=s.base_url, timeout_s=s.timeout_seconds
    )
