"""Credential sources (composition root).

Phases 1-7: every tenant uses the platform's own provider keys.
Phase 8 (Pro): wrap with the tenant vault (modules/credentials): tenant key first, then the
platform key only if the tenant's plan allows a fallback.
"""

from collections.abc import Mapping

from pydantic import SecretStr

from saathi.modules.conversation.adapters.llm.anthropic_llm import AnthropicSettings
from saathi.modules.conversation.adapters.llm.gemini_llm import GeminiSettings


def _reveal(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret else None


class PlatformCredentialSource:
    def __init__(self, keys: Mapping[str, str | None]) -> None:
        self._keys = {provider: key for provider, key in keys.items() if key}

    async def api_key_for(self, tenant_id: str, provider: str) -> str | None:
        return self._keys.get(provider)


def platform_credentials_from_env() -> PlatformCredentialSource:
    # One line per LLM provider adapter.
    return PlatformCredentialSource(
        {
            "gemini": _reveal(GeminiSettings().api_key),
            "anthropic": _reveal(AnthropicSettings().api_key),
        }
    )
