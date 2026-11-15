"""Importing bootstrap registers every adapter; resolvers fail clearly without keys."""

from pathlib import Path
from typing import Any

import httpx
import pytest

from saathi.bootstrap.credentials import PlatformCredentialSource
from saathi.bootstrap.providers import build_llm_resolver
from saathi.modules.channels.adapters import stt_registry, tts_registry
from saathi.modules.conversation.adapters import completion_registry
from saathi.modules.conversation.application.llm_resolver import ModelSelection
from saathi.modules.knowledge.adapters import embedder_registry, parser_registry, reranker_registry
from saathi.platform.config.settings import Settings
from saathi.platform.errors import ConfigurationError
from saathi.platform.providers import ProviderRegistry
from saathi.platform.storage import object_store_registry

SELECTION = ModelSelection(
    provider="anthropic", model_id="m", temperature=0.3, max_output_tokens=100
)


def test_all_adapters_are_registered() -> None:
    assert {"gemini", "anthropic"} <= set(completion_registry.available())
    assert {"gemini", "openai"} <= set(embedder_registry.available())
    assert "cohere" in reranker_registry.available()
    assert "pymupdf" in parser_registry.available()
    assert "sarvam" in stt_registry.available()
    assert "sarvam" in tts_registry.available()
    assert "supabase" in object_store_registry.available()


def test_platform_defaults_follow_adr_0006(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # ignore any developer .env
    for var in ("EMBEDDING_PROVIDER", "STT_PROVIDER", "TTS_PROVIDER", "STORAGE_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    s = Settings()
    assert (s.embedding_provider, s.stt_provider, s.tts_provider, s.storage_provider) == (
        "gemini",
        "sarvam",
        "sarvam",
        "supabase",
    )


@pytest.mark.parametrize(
    ("registry", "name", "kwargs", "env"),
    [
        (embedder_registry, "gemini", {}, ["GEMINI_API_KEY"]),
        (stt_registry, "sarvam", {}, ["SARVAM_API_KEY"]),
        (tts_registry, "sarvam", {}, ["SARVAM_API_KEY"]),
        (
            object_store_registry,
            "supabase",
            {"visibility": "private"},
            ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
        ),
    ],
)
def test_platform_factories_fail_closed_without_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry: ProviderRegistry[Any],
    name: str,
    kwargs: dict[str, str],
    env: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env file here, so only the process environment counts
    for var in env:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ConfigurationError, match=env[0]):
        registry.create(name, http=httpx.AsyncClient(), **kwargs)


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


def test_empty_key_counts_as_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        embedder_registry.create("gemini", http=httpx.AsyncClient())
