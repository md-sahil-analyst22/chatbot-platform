# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules inside BotConfig (lengths, no HTML, temperatures, version status
#                changes).
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From dataclasses — quick classes that mainly hold data: replace = copies an object with some
#   fields changed.
from dataclasses import replace

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: NOW = a fixed time for tests;
#   make_config = builds a test config.
from tests.fakes.builders import NOW, make_config

# From saathi.modules.tenancy.adapters.config_mapper — BotConfig <-> JSON conversion:
#   config_from_json = JSON -> BotConfig; config_to_json = BotConfig -> JSON.
from saathi.modules.tenancy.adapters.config_mapper import config_from_json, config_to_json

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfigVersion = one saved version; Branding = how the widget looks; ConfigStatus =
#   draft/published/archived; GenerationSettings = model and answer style; PromptSettings = the
#   tenant's instructions; ResponseStyle = precise/balanced/friendly.
from saathi.modules.tenancy.domain.bot_config import (
    BotConfigVersion,
    Branding,
    ConfigStatus,
    GenerationSettings,
    PromptSettings,
    ResponseStyle,
)

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ConflictError, ValidationError


# Run the test once per (style, expected temperature) pair:
@pytest.mark.parametrize(
    # the two values each case provides,
    ("style", "temperature"),
    # precise -> 0.1, balanced -> 0.3, friendly -> 0.6.
    [(ResponseStyle.PRECISE, 0.1), (ResponseStyle.BALANCED, 0.3), (ResponseStyle.FRIENDLY, 0.6)],
)
# Each preset gives its documented temperature.
def test_presets_map_to_temperature(style: ResponseStyle, temperature: float) -> None:
    # Must match.
    assert GenerationSettings(style=style).effective_temperature == temperature


# A manual temperature wins, and limits are enforced.
def test_advanced_override_wins_and_is_bounded() -> None:
    # A manual temperature of 0.9.
    g = GenerationSettings(temperature_override=0.9)
    # It's used, and counted as an advanced setting.
    assert g.effective_temperature == 0.9 and g.uses_advanced_settings
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # 1.5 is above the 0-1 range.
        GenerationSettings(temperature_override=1.5)
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # 10 tokens is below the 64 minimum.
        GenerationSettings(max_output_tokens=10)


# Run the test once per bad branding below:
@pytest.mark.parametrize(
    # each case provides `kwargs` (the fields to pass),
    "kwargs",
    # the cases:
    [
        # empty title,
        {"header_title": ""},
        # HTML in the title,
        {"header_title": "<script>x</script>"},
        # '>' in the footer,
        {"header_title": "Ok", "footer_text": "a > b"},
        # a colour that isn't #RRGGBB,
        {"header_title": "Ok", "primary_color": "red"},
        # a hidden control character in the greeting.
        {"header_title": "Ok", "greeting": "line\x00break"},
    ],
)
# Every one of them must be refused.
def test_branding_rejects_unsafe_or_invalid_values(kwargs: dict[str, str]) -> None:
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # Build Branding with those fields.
        Branding(**kwargs)  # type: ignore[arg-type]


# Prompt text limits are enforced.
def test_prompt_limits() -> None:
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # 4001 characters is one over the limit.
        PromptSettings(custom_instructions="x" * 4001)
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # 21 banned topics is one over the limit.
        PromptSettings(banned_topics=tuple(f"t{i}" for i in range(21)))


# draft -> published -> archived, and nothing else.
def test_version_lifecycle() -> None:
    # A version-1 draft (id, tenant, bot, number, status, config, author, time).
    v = BotConfigVersion(uuid4(), uuid4(), uuid4(), 1, ConfigStatus.DRAFT, make_config(), "u", NOW)
    # Publish it.
    live = v.published()
    # Now it's published.
    assert live.status is ConfigStatus.PUBLISHED
    # And publishing then archiving works.
    assert live.archived().status is ConfigStatus.ARCHIVED
    # Expect a ConflictError from the next line:
    with pytest.raises(ConflictError):
        # Publishing something already published is refused.
        live.published()
    # Expect a ConflictError from the next line:
    with pytest.raises(ConflictError):
        # Archiving a draft is refused.
        v.archived()


# Saving to JSON and loading back gives the same config.
def test_json_round_trip() -> None:
    # A test config...
    cfg = make_config()
    # ...changed to use 'advanced' with a manual temperature.
    cfg = replace(
        cfg, generation=GenerationSettings(model_key="advanced", temperature_override=0.4)
    )
    # To JSON and back must be identical.
    assert config_from_json(config_to_json(cfg)) == cfg
