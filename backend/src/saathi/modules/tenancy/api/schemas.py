from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["en", "hi", "bn"]
PUBLIC_KEY_REGEX = r"^pk_[A-Za-z0-9_-]{16,64}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields (e.g. a smuggled tenant_id)


class BotCreate(_Strict):
    name: str = Field(min_length=1, max_length=100)
    persona: str = Field(default="", max_length=2000)
    languages: list[Language] = Field(min_length=1, max_length=3)
    settings: dict[str, Any] = Field(default_factory=dict)


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


class BotConfigIn(_Strict):
    prompt: PromptSettingsIn = Field(default_factory=PromptSettingsIn)
    generation: GenerationSettingsIn = Field(default_factory=GenerationSettingsIn)
    branding: BrandingIn


class BotConfigVersionOut(BaseModel):
    version: int
    status: Literal["draft", "published", "archived"]
    created_by: str
    created_at: datetime
    config: BotConfigIn


class ModelOptionOut(BaseModel):
    key: str
    label: str


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
