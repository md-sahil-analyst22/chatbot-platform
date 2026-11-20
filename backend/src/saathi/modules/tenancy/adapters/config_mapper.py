# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Converts a BotConfig to JSON for storage and back again.
# Why: Configs are stored as JSON. The `schema` number lets future code still read old saved
#      configs (R22).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""BotConfig <-> JSON (stored in bot_config_versions.config). `schema` allows future migrations."""

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfig = one full configuration; Branding = how the widget looks; GenerationSettings =
#   model and answer style; PromptSettings = the tenant's instructions; ResponseStyle =
#   precise/balanced/friendly.
from saathi.modules.tenancy.domain.bot_config import (
    BotConfig,
    Branding,
    GenerationSettings,
    PromptSettings,
    ResponseStyle,
)

# Format version stored with every config, so future code can read old ones.
SCHEMA_VERSION = 1


# BotConfig -> dict (stored in the database).
def config_to_json(config: BotConfig) -> dict[str, Any]:
    # Short names for the three parts.
    p, g, b = config.prompt, config.generation, config.branding
    # Build a plain dictionary (stored as JSON):
    return {
        # the format version,
        "schema": SCHEMA_VERSION,
        # the prompt part:
        "prompt": {
            # persona,
            "persona": p.persona,
            # brand rules,
            "brand_rules": p.brand_rules,
            # custom instructions,
            "custom_instructions": p.custom_instructions,
            # banned topics (as a list).
            "banned_topics": list(p.banned_topics),
        },
        # The generation part:
        "generation": {
            # model key,
            "model_key": g.model_key,
            # style as text,
            "style": g.style.value,
            # manual temperature (or null),
            "temperature_override": g.temperature_override,
            # reply length.
            "max_output_tokens": g.max_output_tokens,
        },
        # The branding part:
        "branding": {
            # title,
            "header_title": b.header_title,
            # subtitle,
            "header_subtitle": b.header_subtitle,
            # footer,
            "footer_text": b.footer_text,
            # greeting,
            "greeting": b.greeting,
            # colour,
            "primary_color": b.primary_color,
            # launcher side,
            "launcher_position": b.launcher_position,
            # logo id as text (or null).
            "logo_asset_id": str(b.logo_asset_id) if b.logo_asset_id else None,
        },
    }


# dict from the database -> BotConfig (missing fields get defaults).
def config_from_json(data: dict[str, Any]) -> BotConfig:
    # Short names for the three parts of the stored JSON.
    p, g, b = data["prompt"], data["generation"], data["branding"]
    # Rebuild the objects (their rules are checked again):
    return BotConfig(
        # prompt part, with defaults for anything missing:
        prompt=PromptSettings(
            # persona (default empty),
            persona=p.get("persona", ""),
            # brand rules,
            brand_rules=p.get("brand_rules", ""),
            # custom instructions,
            custom_instructions=p.get("custom_instructions", ""),
            # banned topics (list -> tuple).
            banned_topics=tuple(p.get("banned_topics", [])),
        ),
        # Generation part:
        generation=GenerationSettings(
            # model key (required),
            model_key=g["model_key"],
            # style (text -> ResponseStyle),
            style=ResponseStyle(g["style"]),
            # manual temperature (None if missing),
            temperature_override=g.get("temperature_override"),
            # reply length (required).
            max_output_tokens=g["max_output_tokens"],
        ),
        # Branding part:
        branding=Branding(
            # title (required),
            header_title=b["header_title"],
            # subtitle (default empty),
            header_subtitle=b.get("header_subtitle", ""),
            # footer,
            footer_text=b.get("footer_text", ""),
            # greeting,
            greeting=b.get("greeting", ""),
            # colour (required),
            primary_color=b["primary_color"],
            # launcher side (default right),
            launcher_position=b.get("launcher_position", "right"),
            # logo id (text -> UUID, or None).
            logo_asset_id=UUID(b["logo_asset_id"]) if b.get("logo_asset_id") else None,
        ),
    )
