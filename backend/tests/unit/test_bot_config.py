from dataclasses import replace
from uuid import uuid4

import pytest
from tests.fakes.builders import NOW, make_config

from saathi.modules.tenancy.adapters.config_mapper import config_from_json, config_to_json
from saathi.modules.tenancy.domain.bot_config import (
    BotConfigVersion,
    Branding,
    ConfigStatus,
    GenerationSettings,
    PromptSettings,
    ResponseStyle,
)
from saathi.platform.errors import ConflictError, ValidationError


@pytest.mark.parametrize(
    ("style", "temperature"),
    [(ResponseStyle.PRECISE, 0.1), (ResponseStyle.BALANCED, 0.3), (ResponseStyle.FRIENDLY, 0.6)],
)
def test_presets_map_to_temperature(style: ResponseStyle, temperature: float) -> None:
    assert GenerationSettings(style=style).effective_temperature == temperature


def test_advanced_override_wins_and_is_bounded() -> None:
    g = GenerationSettings(temperature_override=0.9)
    assert g.effective_temperature == 0.9 and g.uses_advanced_settings
    with pytest.raises(ValidationError):
        GenerationSettings(temperature_override=1.5)
    with pytest.raises(ValidationError):
        GenerationSettings(max_output_tokens=10)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"header_title": ""},
        {"header_title": "<script>x</script>"},
        {"header_title": "Ok", "footer_text": "a > b"},
        {"header_title": "Ok", "primary_color": "red"},
        {"header_title": "Ok", "greeting": "line\x00break"},
    ],
)
def test_branding_rejects_unsafe_or_invalid_values(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Branding(**kwargs)  # type: ignore[arg-type]


def test_prompt_limits() -> None:
    with pytest.raises(ValidationError):
        PromptSettings(custom_instructions="x" * 4001)
    with pytest.raises(ValidationError):
        PromptSettings(banned_topics=tuple(f"t{i}" for i in range(21)))


def test_version_lifecycle() -> None:
    v = BotConfigVersion(uuid4(), uuid4(), uuid4(), 1, ConfigStatus.DRAFT, make_config(), "u", NOW)
    live = v.published()
    assert live.status is ConfigStatus.PUBLISHED
    assert live.archived().status is ConfigStatus.ARCHIVED
    with pytest.raises(ConflictError):
        live.published()
    with pytest.raises(ConflictError):
        v.archived()


def test_json_round_trip() -> None:
    cfg = make_config()
    cfg = replace(
        cfg, generation=GenerationSettings(model_key="advanced", temperature_override=0.4)
    )
    assert config_from_json(config_to_json(cfg)) == cfg
