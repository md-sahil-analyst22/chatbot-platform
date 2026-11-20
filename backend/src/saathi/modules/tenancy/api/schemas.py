# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The exact shapes of JSON the API accepts and returns for bots and configs.
# Security: 🔒 Input models forbid unknown fields (so nobody can sneak in a tenant_id) and limit
#           every length (R19).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From typing — type-hint helpers: Annotated = a type plus extra info (e.g. a FastAPI
#   dependency); Any = any type; Literal = only these exact values.
from typing import Annotated, Any, Literal

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From pydantic — checks data against declared types and rules: BaseModel = parent class for
#   request/response shapes; ConfigDict = model options such as extra='forbid'; Field = per-field
#   rules (length, range, default); model_validator = a check that looks at the whole model at
#   once.
from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["en", "hi", "bn"]
PUBLIC_KEY_REGEX = r"^pk_[A-Za-z0-9_-]{16,64}$"


# Parent for input models: unknown fields -> 422 error.
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields (e.g. a smuggled tenant_id)


# Body of POST /api/v1/bots.
class BotCreate(_Strict):
    name: str = Field(min_length=1, max_length=100)
    persona: str = Field(default="", max_length=2000)
    languages: list[Language] = Field(min_length=1, max_length=3)
    settings: dict[str, Any] = Field(default_factory=dict)


# Body of PATCH /api/v1/bots/{id}; at least one field required.
class BotUpdate(_Strict):
    """PATCH body: send only the fields to change."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    persona: str | None = Field(default=None, max_length=2000)
    languages: list[Language] | None = Field(default=None, min_length=1, max_length=3)
    settings: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "BotUpdate":
        if not self.model_fields_set:
            raise ValueError("send at least one field to change")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


# What the API returns for a bot.
class BotOut(BaseModel):
    id: UUID
    name: str
    persona: str
    languages: list[str]
    public_key: str
    settings: dict[str, Any]


# ----------------------------------------------------------------- Bot Studio configuration
class PromptSettingsIn(_Strict):
    persona: str = Field(default="", max_length=1000)
    brand_rules: str = Field(default="", max_length=2000)
    custom_instructions: str = Field(default="", max_length=4000)
    banned_topics: list[Annotated[str, Field(max_length=100)]] = Field(
        default_factory=list, max_length=20
    )


class GenerationSettingsIn(_Strict):
    model_key: str = Field(default="standard", pattern=r"^[a-z0-9-]{1,40}$")
    style: Literal["precise", "balanced", "friendly"] = "balanced"
    temperature_override: float | None = Field(default=None, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=600, ge=64, le=2000)


class BrandingIn(_Strict):
    header_title: str = Field(min_length=1, max_length=60)
    header_subtitle: str = Field(default="", max_length=80)
    footer_text: str = Field(default="", max_length=120)
    greeting: str = Field(default="", max_length=300)
    primary_color: str = Field(default="#0F766E", pattern=r"^#[0-9A-Fa-f]{6}$")
    launcher_position: Literal["right", "left"] = "right"
    logo_asset_id: UUID | None = None


# Body for saving a configuration draft.
class BotConfigIn(_Strict):
    prompt: PromptSettingsIn = Field(default_factory=PromptSettingsIn)
    generation: GenerationSettingsIn = Field(default_factory=GenerationSettingsIn)
    branding: BrandingIn


# What the API returns for a config version.
class BotConfigVersionOut(BaseModel):
    version: int
    status: Literal["draft", "published", "archived"]
    created_by: str
    created_at: datetime
    config: BotConfigIn


# One choosable model (no vendor model ids).
class ModelOptionOut(BaseModel):
    key: str
    label: str


# 🔒 What the public widget gets: display fields only (R10).
class PublicWidgetConfigOut(BaseModel):
    """Public look of a widget only (R10): no prompts, model, plan or internal ids."""

    header_title: str
    header_subtitle: str
    footer_text: str
    greeting: str
    primary_color: str
    launcher_position: str
    logo_url: str | None
    languages: list[str]
