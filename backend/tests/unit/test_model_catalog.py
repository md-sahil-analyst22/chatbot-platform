import pytest
from tests.fakes.builders import make_catalog

from saathi.modules.conversation.application.llm_resolver import select_model
from saathi.platform.config.model_catalog import CatalogSettings, default_catalog
from saathi.platform.errors import ValidationError


def test_plan_filtering_and_unknown_key() -> None:
    catalog = make_catalog()
    assert catalog.is_allowed("standard", "starter")
    assert not catalog.is_allowed("advanced", "starter")
    with pytest.raises(ValidationError):
        catalog.get("gpt-unknown")


def test_default_catalog_only_lists_configured_models() -> None:
    catalog = default_catalog(
        CatalogSettings(anthropic_model_small="s", anthropic_model_large=None)
    )
    assert [o.key for o in catalog.options_for_plan("pro")] == ["standard"]


def test_select_model_caps_tokens_to_option_limit() -> None:
    sel = select_model(make_catalog(), "standard", temperature=0.3, max_output_tokens=5000)
    assert (sel.provider, sel.model_id, sel.max_output_tokens) == ("anthropic", "small-model", 1000)
