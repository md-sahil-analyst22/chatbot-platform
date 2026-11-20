# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The model catalog: which models appear and which plan may use them.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: make_catalog = builds a test
#   catalog.
from tests.fakes.builders import make_catalog

# From saathi.modules.conversation.application.llm_resolver — picks the AI model and key for a
#   bot: select_model = catalog key -> vendor + model.
from saathi.modules.conversation.application.llm_resolver import select_model

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   CatalogSettings = model ids from .env; default_catalog = builds the catalog.
from saathi.platform.config.model_catalog import CatalogSettings, default_catalog

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError


def test_plan_filtering_and_unknown_key() -> None:
    catalog = make_catalog()
    assert catalog.is_allowed("standard", "starter")
    assert not catalog.is_allowed("advanced", "starter")
    with pytest.raises(ValidationError):
        catalog.get("gpt-unknown")


def test_default_catalog_only_lists_configured_models() -> None:
    catalog = default_catalog(
        CatalogSettings(
            gemini_model_small="g-small",
            gemini_model_large=None,
            anthropic_model_small="c-small",
            anthropic_model_large=None,
        )
    )
    assert [o.key for o in catalog.options_for_plan("pro")] == ["standard", "claude-standard"]


def test_gemini_owns_the_plain_catalog_keys() -> None:
    catalog = default_catalog(
        CatalogSettings(
            gemini_model_small="g-small",
            gemini_model_large="g-large",
            anthropic_model_small=None,
            anthropic_model_large=None,
        )
    )
    standard, advanced = catalog.get("standard"), catalog.get("advanced")
    assert (standard.provider, standard.model_id) == ("gemini", "g-small")
    assert (advanced.provider, advanced.model_id) == ("gemini", "g-large")
    assert catalog.is_allowed("advanced", "growth")
    assert not catalog.is_allowed("advanced", "starter")


def test_select_model_caps_tokens_to_option_limit() -> None:
    sel = select_model(make_catalog(), "standard", temperature=0.3, max_output_tokens=5000)
    assert (sel.provider, sel.model_id, sel.max_output_tokens) == ("anthropic", "small-model", 1000)
