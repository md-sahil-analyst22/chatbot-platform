"""Per-bot model resolution: catalog key + bot settings -> a ready CompletionClient."""

from dataclasses import dataclass
from typing import Protocol

from saathi.modules.conversation.ports.credentials import CredentialSource
from saathi.modules.conversation.ports.llm import CompletionClient
from saathi.platform.config.model_catalog import ModelCatalog
from saathi.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class ModelSelection:
    provider: str
    model_id: str
    temperature: float
    max_output_tokens: int


def select_model(
    catalog: ModelCatalog, model_key: str, *, temperature: float, max_output_tokens: int
) -> ModelSelection:
    option = catalog.get(model_key)
    return ModelSelection(
        provider=option.provider,
        model_id=option.model_id,
        temperature=temperature,
        max_output_tokens=min(max_output_tokens, option.max_output_tokens),
    )


class CompletionClientFactory(Protocol):
    def __call__(self, provider: str, api_key: str) -> CompletionClient: ...


class LlmResolver:
    def __init__(self, factory: CompletionClientFactory, credentials: CredentialSource) -> None:
        self._factory = factory
        self._credentials = credentials

    async def resolve(self, tenant_id: str, selection: ModelSelection) -> CompletionClient:
        api_key = await self._credentials.api_key_for(tenant_id, selection.provider)
        if not api_key:
            # Fail closed: never fall back to another tenant's or an unintended key.
            raise ConfigurationError(f"no API key available for provider '{selection.provider}'")
        return self._factory(selection.provider, api_key)
