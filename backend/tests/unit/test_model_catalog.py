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


# Plans filter models, and unknown keys are refused.
def test_plan_filtering_and_unknown_key() -> None:
    # The two-model test catalog.
    catalog = make_catalog()
    # 'standard' is allowed on starter.
    assert catalog.is_allowed("standard", "starter")
    # 'advanced' is not.
    assert not catalog.is_allowed("advanced", "starter")
    # Expect 422...
    with pytest.raises(ValidationError):
        # ...for a key that isn't in the catalog.
        catalog.get("gpt-unknown")


# Only models with a configured id appear.
def test_default_catalog_only_lists_configured_models() -> None:
    # Build the real catalog from test settings:
    catalog = default_catalog(
        # settings with
        CatalogSettings(
            # a small Gemini model,
            gemini_model_small="g-small",
            # no large Gemini model,
            gemini_model_large=None,
            # a small Claude model,
            anthropic_model_small="c-small",
            # no large Claude model.
            anthropic_model_large=None,
        )
    )
    # So 'pro' sees exactly the two configured ones.
    assert [o.key for o in catalog.options_for_plan("pro")] == ["standard", "claude-standard"]


# Gemini gets the plain 'standard'/'advanced' keys.
def test_gemini_owns_the_plain_catalog_keys() -> None:
    # Build the catalog from settings:
    catalog = default_catalog(
        # settings with
        CatalogSettings(
            # both Gemini models,
            gemini_model_small="g-small",
            # (same)
            gemini_model_large="g-large",
            # no Claude models,
            anthropic_model_small=None,
            # (same).
            anthropic_model_large=None,
        )
    )
    # Look both keys up.
    standard, advanced = catalog.get("standard"), catalog.get("advanced")
    # 'standard' is Gemini's small model.
    assert (standard.provider, standard.model_id) == ("gemini", "g-small")
    # 'advanced' is Gemini's large model.
    assert (advanced.provider, advanced.model_id) == ("gemini", "g-large")
    # 'advanced' is allowed on growth...
    assert catalog.is_allowed("advanced", "growth")
    # ...but not on starter.
    assert not catalog.is_allowed("advanced", "starter")


# A bot can't ask for longer replies than the catalog allows.
def test_select_model_caps_tokens_to_option_limit() -> None:
    # Ask for 5000 tokens.
    sel = select_model(make_catalog(), "standard", temperature=0.3, max_output_tokens=5000)
    # Capped at the catalog's 1000.
    assert (sel.provider, sel.model_id, sel.max_output_tokens) == ("anthropic", "small-model", 1000)
