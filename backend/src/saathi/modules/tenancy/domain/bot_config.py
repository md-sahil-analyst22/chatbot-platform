# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Everything a tenant edits in Bot Studio: instructions, answer style, model, colours,
#       greeting...
# Versions: Each save creates a numbered version: draft -> published -> archived. Only one
#           version per bot is published (live) at a time.
# Safety: 🔒 Text fields are checked here (length, no control characters, no HTML in UI text)
#         before anything is saved.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Bot configuration: everything a tenant edits in Bot Studio.

Configurations are immutable versions. Saving creates a new DRAFT version; publishing makes one
version live; rollback copies an old version into a new draft and publishes it. History is never
rewritten, so every change is auditable and reversible.
"""

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from saathi.platform.errors import ConflictError, ValidationError

_HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
_MODEL_KEY = re.compile(r"[a-z0-9-]{1,40}")


# Preset answer styles a tenant can pick (each maps to a temperature).
class ResponseStyle(StrEnum):
    """Presets for non-technical users. Each maps to a sampling temperature."""

    PRECISE = "precise"
    BALANCED = "balanced"
    FRIENDLY = "friendly"


STYLE_TEMPERATURE: dict[ResponseStyle, float] = {
    ResponseStyle.PRECISE: 0.1,
    ResponseStyle.BALANCED: 0.3,
    ResponseStyle.FRIENDLY: 0.6,
}


# The life cycle of one version: draft, published, archived.
class ConfigStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Shared check for long text: max length and no hidden control characters.
def _plain_text(value: str, field_name: str, max_len: int, *, allow_newlines: bool) -> None:
    if len(value) > max_len:
        raise ValidationError(f"{field_name} must be at most {max_len} characters")
    for ch in value:
        if ch in "\n\t" and allow_newlines:
            continue
        if unicodedata.category(ch) == "Cc":
            raise ValidationError(f"{field_name} contains control characters")


# Shared check for short text shown in the widget: also no '<' or '>' (no HTML).
def _ui_text(value: str, field_name: str, max_len: int) -> None:
    """Short text shown in the widget. Rendered as text, and angle brackets are refused too."""
    _plain_text(value, field_name, max_len, allow_newlines=False)
    if "<" in value or ">" in value:
        raise ValidationError(f"{field_name} must not contain '<' or '>'")


@dataclass(frozen=True, slots=True)
# The tenant's instructions to the bot and example questions.
class PromptSettings:
    """Tenant-authored instructions. Always placed BELOW the platform's fixed safety rules."""

    persona: str = ""
    brand_rules: str = ""
    custom_instructions: str = ""
    banned_topics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _plain_text(self.persona, "persona", 1000, allow_newlines=True)
        _plain_text(self.brand_rules, "brand_rules", 2000, allow_newlines=True)
        _plain_text(self.custom_instructions, "custom_instructions", 4000, allow_newlines=True)
        if len(self.banned_topics) > 20:
            raise ValidationError("at most 20 banned topics")
        for topic in self.banned_topics:
            _plain_text(topic, "banned topic", 100, allow_newlines=False)


@dataclass(frozen=True, slots=True)
# Which model (catalog key), answer style and optional advanced values.
class GenerationSettings:
    model_key: str = "standard"
    style: ResponseStyle = ResponseStyle.BALANCED
    temperature_override: float | None = None  # advanced setting
    max_output_tokens: int = 600

    def __post_init__(self) -> None:
        if not _MODEL_KEY.fullmatch(self.model_key):
            raise ValidationError("invalid model key")
        if self.temperature_override is not None and not 0.0 <= self.temperature_override <= 1.0:
            raise ValidationError("temperature must be between 0 and 1")
        if not 64 <= self.max_output_tokens <= 2000:
            raise ValidationError("max_output_tokens must be between 64 and 2000")

    @property
    # The 'creativity' number actually sent to the model.
    def effective_temperature(self) -> float:
        if self.temperature_override is not None:
            return self.temperature_override
        return STYLE_TEMPERATURE[self.style]

    @property
    # True if the tenant changed advanced values by hand.
    def uses_advanced_settings(self) -> bool:
        return self.temperature_override is not None


@dataclass(frozen=True, slots=True)
# How the widget looks: title, colours, greeting, logo, position.
class Branding:
    header_title: str
    header_subtitle: str = ""
    footer_text: str = ""
    greeting: str = ""
    primary_color: str = "#0F766E"
    launcher_position: Literal["right", "left"] = "right"
    logo_asset_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.header_title.strip():
            raise ValidationError("header_title must not be empty")
        _ui_text(self.header_title, "header_title", 60)
        _ui_text(self.header_subtitle, "header_subtitle", 80)
        _ui_text(self.footer_text, "footer_text", 120)
        _ui_text(self.greeting, "greeting", 300)
        if not _HEX_COLOR.fullmatch(self.primary_color):
            raise ValidationError("primary_color must be a hex colour like #0F766E")
        if self.launcher_position not in ("right", "left"):
            raise ValidationError("launcher_position must be 'right' or 'left'")


@dataclass(frozen=True, slots=True)
# One complete configuration = prompt + generation + branding.
class BotConfig:
    prompt: PromptSettings
    generation: GenerationSettings
    branding: Branding


@dataclass(frozen=True, slots=True)
# One saved, numbered version of a BotConfig, with its status.
class BotConfigVersion:
    id: UUID
    tenant_id: UUID
    bot_id: UUID
    version: int
    status: ConfigStatus
    config: BotConfig
    created_by: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValidationError("version must be >= 1")

    # Return this version marked as live.
    def published(self) -> "BotConfigVersion":
        if self.status is not ConfigStatus.DRAFT:
            raise ConflictError("only a draft can be published")
        return replace(self, status=ConfigStatus.PUBLISHED)

    # Return this version marked as old (no longer live).
    def archived(self) -> "BotConfigVersion":
        if self.status is not ConfigStatus.PUBLISHED:
            raise ConflictError("only the published version can be archived")
        return replace(self, status=ConfigStatus.ARCHIVED)
