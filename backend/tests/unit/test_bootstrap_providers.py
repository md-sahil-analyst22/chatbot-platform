"""Importing bootstrap registers every adapter; resolvers fail clearly without keys."""

import httpx
import pytest

from saathi.bootstrap.credentials import PlatformCredentialSource
from saathi.bootstrap.providers import build_llm_resolver
from saathi.modules.conversation.adapters import completion_registry
from saathi.modules.conversation.application.llm_resolver import ModelSelection
from saathi.modules.knowledge.adapters import embedder_registry, parser_registry, reranker_registry
from saathi.platform.errors import ConfigurationError

SELECTION = ModelSelection(
    provider="anthropic", model_id="m", temperature=0.3, max_output_tokens=100
)


def test_all_adapters_are_registered() -> None:
    assert "anthropic" in completion_registry.available()
    assert "openai" in embedder_registry.available()
    assert "cohere" in reranker_registry.available()
    assert "pymupdf" in parser_registry.available()


def test_factory_fails_clearly_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        embedder_registry.create("openai", http=httpx.AsyncClient())


async def test_llm_resolver_builds_client_with_platform_key() -> None:
    resolver = build_llm_resolver(httpx.AsyncClient(), PlatformCredentialSource({"anthropic": "k"}))
    client = await resolver.resolve("tenant-1", SELECTION)
    assert hasattr(client, "complete")


async def test_llm_resolver_fails_closed_without_key() -> None:
    resolver = build_llm_resolver(httpx.AsyncClient(), PlatformCredentialSource({}))
    with pytest.raises(ConfigurationError, match="anthropic"):
        await resolver.resolve("tenant-1", SELECTION)
