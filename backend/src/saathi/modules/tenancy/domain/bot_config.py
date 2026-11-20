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

# re — regular expressions (text patterns).
import re

# unicodedata — facts about Unicode characters.
import unicodedata

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; replace = copies an object with some fields changed.
from dataclasses import dataclass, replace

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From typing — type-hint helpers: Literal = only these exact values.
from typing import Literal

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ConflictError, ValidationError

# A colour like #0F766E: '#' and 6 hex digits.
_HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
# Model keys: 1-40 lowercase letters, digits or '-'.
_MODEL_KEY = re.compile(r"[a-z0-9-]{1,40}")


# Preset answer styles a tenant can pick (each maps to a temperature).
class ResponseStyle(StrEnum):
    """Presets for non-technical users. Each maps to a sampling temperature."""

    # Sticks to the facts.
    PRECISE = "precise"
    # The default middle ground.
    BALANCED = "balanced"
    # Warmer and chattier.
    FRIENDLY = "friendly"


# Each style's 'temperature' (higher = more creative, less predictable):
STYLE_TEMPERATURE: dict[ResponseStyle, float] = {
    # precise -> 0.1,
    ResponseStyle.PRECISE: 0.1,
    # balanced -> 0.3,
    ResponseStyle.BALANCED: 0.3,
    # friendly -> 0.6.
    ResponseStyle.FRIENDLY: 0.6,
}


# The life cycle of one version: draft, published, archived.
class ConfigStatus(StrEnum):
    # Saved but not live.
    DRAFT = "draft"
    # Live: the widget uses this one.
    PUBLISHED = "published"
    # Replaced by a newer published version.
    ARCHIVED = "archived"


# Shared check for long text: max length and no hidden control characters.
def _plain_text(value: str, field_name: str, max_len: int, *, allow_newlines: bool) -> None:
    # Too long:
    if len(value) > max_len:
        # refuse.
        raise ValidationError(f"{field_name} must be at most {max_len} characters")
    # Check every character:
    for ch in value:
        # newlines and tabs are fine where newlines are allowed...
        if ch in "\n\t" and allow_newlines:
            # ...so skip them.
            continue
        # Any other invisible control character (category 'Cc')...
        if unicodedata.category(ch) == "Cc":
            # ...is refused.
            raise ValidationError(f"{field_name} contains control characters")


# Shared check for short text shown in the widget: also no '<' or '>' (no HTML).
def _ui_text(value: str, field_name: str, max_len: int) -> None:
    """Short text shown in the widget. Rendered as text, and angle brackets are refused too."""
    # Same checks as above, newlines not allowed.
    _plain_text(value, field_name, max_len, allow_newlines=False)
    # 🔒 Text shown in the widget must not contain < or > (no HTML).
    if "<" in value or ">" in value:
        # Refuse it.
        raise ValidationError(f"{field_name} must not contain '<' or '>'")


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# The tenant's instructions to the bot and example questions.
class PromptSettings:
    """Tenant-authored instructions. Always placed BELOW the platform's fixed safety rules."""

    # Personality and tone.
    persona: str = ""
    # Brand rules (words to use or avoid...).
    brand_rules: str = ""
    # Extra instructions.
    custom_instructions: str = ""
    # Topics the bot must never discuss.
    banned_topics: tuple[str, ...] = ()

    # Checked automatically when the object is created:
    def __post_init__(self) -> None:
        # persona: up to 1000 characters,
        _plain_text(self.persona, "persona", 1000, allow_newlines=True)
        # brand rules: up to 2000,
        _plain_text(self.brand_rules, "brand_rules", 2000, allow_newlines=True)
        # custom instructions: up to 4000,
        _plain_text(self.custom_instructions, "custom_instructions", 4000, allow_newlines=True)
        # at most 20 banned topics...
        if len(self.banned_topics) > 20:
            # ...otherwise refuse;
            raise ValidationError("at most 20 banned topics")
        # each topic...
        for topic in self.banned_topics:
            # ...up to 100 characters, on one line.
            _plain_text(topic, "banned topic", 100, allow_newlines=False)


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# Which model (catalog key), answer style and optional advanced values.
class GenerationSettings:
    # Which catalog model (default 'standard').
    model_key: str = "standard"
    # Answer style (default balanced).
    style: ResponseStyle = ResponseStyle.BALANCED
    temperature_override: float | None = None  # advanced setting
    # Longest reply in tokens (default 600).
    max_output_tokens: int = 600

    # Checked automatically when the object is created:
    def __post_init__(self) -> None:
        # the model key must have the right format...
        if not _MODEL_KEY.fullmatch(self.model_key):
            # ...otherwise refuse;
            raise ValidationError("invalid model key")
        # a manual temperature must be between 0 and 1...
        if self.temperature_override is not None and not 0.0 <= self.temperature_override <= 1.0:
            # ...otherwise refuse;
            raise ValidationError("temperature must be between 0 and 1")
        # the reply length must be 64-2000 tokens...
        if not 64 <= self.max_output_tokens <= 2000:
            # ...otherwise refuse.
            raise ValidationError("max_output_tokens must be between 64 and 2000")

    # @property: read it like a field (settings.effective_temperature), no brackets.
    @property
    # The 'creativity' number actually sent to the model.
    def effective_temperature(self) -> float:
        # A manual value wins...
        if self.temperature_override is not None:
            # ...so use it.
            return self.temperature_override
        # Otherwise use the style's preset value.
        return STYLE_TEMPERATURE[self.style]

    # Read like a field.
    @property
    # True if the tenant changed advanced values by hand.
    def uses_advanced_settings(self) -> bool:
        # True if a manual temperature was set.
        return self.temperature_override is not None


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# How the widget looks: title, colours, greeting, logo, position.
class Branding:
    # Title at the top of the chat window (required).
    header_title: str
    # Small line under the title.
    header_subtitle: str = ""
    # Text at the bottom of the window.
    footer_text: str = ""
    # First message the bot shows.
    greeting: str = ""
    # Main colour (default teal).
    primary_color: str = "#0F766E"
    # Launcher button on the right or left.
    launcher_position: Literal["right", "left"] = "right"
    # Uploaded logo, if any.
    logo_asset_id: UUID | None = None

    # Checked automatically when the object is created:
    def __post_init__(self) -> None:
        # the title must not be blank...
        if not self.header_title.strip():
            # ...otherwise refuse;
            raise ValidationError("header_title must not be empty")
        # title: max 60 characters, no < or >;
        _ui_text(self.header_title, "header_title", 60)
        # subtitle: max 80;
        _ui_text(self.header_subtitle, "header_subtitle", 80)
        # footer: max 120;
        _ui_text(self.footer_text, "footer_text", 120)
        # greeting: max 300;
        _ui_text(self.greeting, "greeting", 300)
        # the colour must look like #RRGGBB...
        if not _HEX_COLOR.fullmatch(self.primary_color):
            # ...otherwise refuse;
            raise ValidationError("primary_color must be a hex colour like #0F766E")
        # the position must be right or left...
        if self.launcher_position not in ("right", "left"):
            # ...otherwise refuse.
            raise ValidationError("launcher_position must be 'right' or 'left'")


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# One complete configuration = prompt + generation + branding.
class BotConfig:
    # The instructions part.
    prompt: PromptSettings
    # The model/style part.
    generation: GenerationSettings
    # The look-and-feel part.
    branding: Branding


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# One saved, numbered version of a BotConfig, with its status.
class BotConfigVersion:
    # This version's own id.
    id: UUID
    # 🔒 The workspace that owns it.
    tenant_id: UUID
    # The bot it belongs to.
    bot_id: UUID
    # Its number: 1, 2, 3... per bot.
    version: int
    # draft, published or archived.
    status: ConfigStatus
    # The configuration itself.
    config: BotConfig
    # Who saved it (user id).
    created_by: str
    # When it was saved.
    created_at: datetime

    # Checked automatically when the object is created:
    def __post_init__(self) -> None:
        # version numbers start at 1...
        if self.version < 1:
            # ...otherwise refuse.
            raise ValidationError("version must be >= 1")

    # Return this version marked as live.
    def published(self) -> "BotConfigVersion":
        # Only a draft may go live...
        if self.status is not ConfigStatus.DRAFT:
            # ...anything else is a conflict (409).
            raise ConflictError("only a draft can be published")
        # A copy marked as published.
        return replace(self, status=ConfigStatus.PUBLISHED)

    # Return this version marked as old (no longer live).
    def archived(self) -> "BotConfigVersion":
        # Only the live version may be archived...
        if self.status is not ConfigStatus.PUBLISHED:
            # ...anything else is a conflict.
            raise ConflictError("only the published version can be archived")
        # A copy marked as archived.
        return replace(self, status=ConfigStatus.ARCHIVED)
