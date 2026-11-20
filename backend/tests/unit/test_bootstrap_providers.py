# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Every vendor adapter registers itself, and missing keys give clear errors.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Importing bootstrap registers every adapter; resolvers fail clearly without keys."""

# From pathlib — file and folder paths: Path = a file or folder path.
from pathlib import Path

# From typing — type-hint helpers: Any = any type.
from typing import Any

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From saathi.bootstrap.credentials — where the platform's own vendor API keys come from:
#   PlatformCredentialSource = hands out the platform's own vendor keys.
from saathi.bootstrap.credentials import PlatformCredentialSource

# From saathi.bootstrap.providers — connects vendor adapters to their registries:
#   build_llm_resolver = creates the AI-model resolver.
from saathi.bootstrap.providers import build_llm_resolver

# From saathi.modules.channels.adapters — speech vendor registries: stt_registry =
#   speech-to-text vendors; tts_registry = text-to-speech vendors.
from saathi.modules.channels.adapters import stt_registry, tts_registry

# From saathi.modules.conversation.adapters — the AI language-model registry:
#   completion_registry = the AI language-model registry.
from saathi.modules.conversation.adapters import completion_registry

# From saathi.modules.conversation.application.llm_resolver — picks the AI model and key for a
#   bot: ModelSelection = chosen vendor + model + limits.
from saathi.modules.conversation.application.llm_resolver import ModelSelection

# From saathi.modules.knowledge.adapters — parser, embedder and reranker registries:
#   embedder_registry = embedder vendors; parser_registry = document parsers; reranker_registry =
#   reranker vendors.
from saathi.modules.knowledge.adapters import embedder_registry, parser_registry, reranker_registry

# From saathi.platform.config.settings — the app's core settings: Settings = the settings class.
from saathi.platform.config.settings import Settings

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing.
from saathi.platform.errors import ConfigurationError

# From saathi.platform.providers — the vendor registry: ProviderRegistry = the 'phone book' of
#   vendor adapters.
from saathi.platform.providers import ProviderRegistry

# From saathi.platform.storage — file storage contract and registry: object_store_registry =
#   file storage vendors.
from saathi.platform.storage import object_store_registry

# A test model selection: Anthropic model 'm'.
SELECTION = ModelSelection(
    provider="anthropic", model_id="m", temperature=0.3, max_output_tokens=100
)


# Importing bootstrap registers every vendor adapter.
def test_all_adapters_are_registered() -> None:
    # Gemini and Anthropic chat models,
    assert {"gemini", "anthropic"} <= set(completion_registry.available())
    # Gemini and OpenAI embedders,
    assert {"gemini", "openai"} <= set(embedder_registry.available())
    # Cohere reranker,
    assert "cohere" in reranker_registry.available()
    # PyMuPDF parser,
    assert "pymupdf" in parser_registry.available()
    # Sarvam speech-to-text,
    assert "sarvam" in stt_registry.available()
    # Sarvam text-to-speech,
    assert "sarvam" in tts_registry.available()
    # Supabase storage.
    assert "supabase" in object_store_registry.available()


# With nothing configured, the defaults are the vendors chosen in ADR-0006.
def test_platform_defaults_follow_adr_0006(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # ignore any developer .env
    # Remove any of these variables from the environment for this test...
    for var in ("EMBEDDING_PROVIDER", "STT_PROVIDER", "TTS_PROVIDER", "STORAGE_PROVIDER"):
        # ...(no error if one isn't set).
        monkeypatch.delenv(var, raising=False)
    # Read the settings.
    s = Settings()
    # The defaults must be:
    assert (s.embedding_provider, s.stt_provider, s.tts_provider, s.storage_provider) == (
        # embeddings: gemini,
        "gemini",
        # speech-to-text: sarvam,
        "sarvam",
        # text-to-speech: sarvam,
        "sarvam",
        # storage: supabase.
        "supabase",
    )


# Run once per vendor factory below:
@pytest.mark.parametrize(
    # each case gives the registry, the name, extra arguments and the variables it needs,
    ("registry", "name", "kwargs", "env"),
    # the cases:
    [
        # Gemini embedder needs GEMINI_API_KEY,
        (embedder_registry, "gemini", {}, ["GEMINI_API_KEY"]),
        # Sarvam speech-to-text needs SARVAM_API_KEY,
        (stt_registry, "sarvam", {}, ["SARVAM_API_KEY"]),
        # Sarvam text-to-speech needs SARVAM_API_KEY,
        (tts_registry, "sarvam", {}, ["SARVAM_API_KEY"]),
        # Supabase storage needs:
        (
            # (registry)
            object_store_registry,
            # (name)
            "supabase",
            # (private bucket)
            {"visibility": "private"},
            # SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
            ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
        ),
    ],
)
# 🔒 Without their keys, factories refuse to build (fail closed).
def test_platform_factories_fail_closed_without_keys(
    # monkeypatch changes the environment just for this test,
    monkeypatch: pytest.MonkeyPatch,
    # tmp_path is an empty temporary folder,
    tmp_path: Path,
    # the registry (from the case),
    registry: ProviderRegistry[Any],
    # the vendor name,
    name: str,
    # extra arguments,
    kwargs: dict[str, str],
    # the variables it needs.
    env: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env file here, so only the process environment counts
    # Remove each needed variable...
    for var in env:
        # ...from the environment.
        monkeypatch.delenv(var, raising=False)
    # Expect a ConfigurationError naming the first missing variable...
    with pytest.raises(ConfigurationError, match=env[0]):
        # ...when building the adapter.
        registry.create(name, http=httpx.AsyncClient(), **kwargs)


# The OpenAI embedder also refuses without its key.
def test_factory_fails_clearly_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make sure OPENAI_API_KEY is not set.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Expect an error naming it...
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        # ...when building the adapter.
        embedder_registry.create("openai", http=httpx.AsyncClient())


# With a platform key, the resolver builds a working client.
async def test_llm_resolver_builds_client_with_platform_key() -> None:
    # A resolver whose only key is a fake Anthropic one.
    resolver = build_llm_resolver(httpx.AsyncClient(), PlatformCredentialSource({"anthropic": "k"}))
    # Resolve the client for a tenant.
    client = await resolver.resolve("tenant-1", SELECTION)
    # It's a real client (it has complete()).
    assert hasattr(client, "complete")


# 🔒 Without a key, the resolver refuses (never falls back to another key).
async def test_llm_resolver_fails_closed_without_key() -> None:
    # A resolver with no keys at all.
    resolver = build_llm_resolver(httpx.AsyncClient(), PlatformCredentialSource({}))
    # Expect an error naming 'anthropic'...
    with pytest.raises(ConfigurationError, match="anthropic"):
        # ...when resolving.
        await resolver.resolve("tenant-1", SELECTION)


# 🔒 An empty key counts as missing.
def test_empty_key_counts_as_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Work in an empty folder (no .env).
    monkeypatch.chdir(tmp_path)
    # Set GEMINI_API_KEY to empty text.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    # Expect an error naming GEMINI_API_KEY...
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        # ...when building the Gemini embedder.
        embedder_registry.create("gemini", http=httpx.AsyncClient())
