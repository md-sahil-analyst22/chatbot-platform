"""BotConfig <-> JSON (stored in bot_config_versions.config). `schema` allows future migrations."""

from typing import Any
from uuid import UUID

from saathi.modules.tenancy.domain.bot_config import (
    BotConfig,
    Branding,
    GenerationSettings,
    PromptSettings,
    ResponseStyle,
)

SCHEMA_VERSION = 1


def config_to_json(config: BotConfig) -> dict[str, Any]:
    p, g, b = config.prompt, config.generation, config.branding
    return {
        "schema": SCHEMA_VERSION,
        "prompt": {
            "persona": p.persona,
            "brand_rules": p.brand_rules,
            "custom_instructions": p.custom_instructions,
            "banned_topics": list(p.banned_topics),
        },
        "generation": {
            "model_key": g.model_key,
            "style": g.style.value,
            "temperature_override": g.temperature_override,
            "max_output_tokens": g.max_output_tokens,
        },
        "branding": {
            "header_title": b.header_title,
            "header_subtitle": b.header_subtitle,
            "footer_text": b.footer_text,
            "greeting": b.greeting,
            "primary_color": b.primary_color,
            "launcher_position": b.launcher_position,
            "logo_asset_id": str(b.logo_asset_id) if b.logo_asset_id else None,
        },
    }


def config_from_json(data: dict[str, Any]) -> BotConfig:
    p, g, b = data["prompt"], data["generation"], data["branding"]
    return BotConfig(
        prompt=PromptSettings(
            persona=p.get("persona", ""),
            brand_rules=p.get("brand_rules", ""),
            custom_instructions=p.get("custom_instructions", ""),
            banned_topics=tuple(p.get("banned_topics", [])),
        ),
        generation=GenerationSettings(
            model_key=g["model_key"],
            style=ResponseStyle(g["style"]),
            temperature_override=g.get("temperature_override"),
            max_output_tokens=g["max_output_tokens"],
        ),
        branding=Branding(
            header_title=b["header_title"],
            header_subtitle=b.get("header_subtitle", ""),
            footer_text=b.get("footer_text", ""),
            greeting=b.get("greeting", ""),
            primary_color=b["primary_color"],
            launcher_position=b.get("launcher_position", "right"),
            logo_asset_id=UUID(b["logo_asset_id"]) if b.get("logo_asset_id") else None,
        ),
    )
