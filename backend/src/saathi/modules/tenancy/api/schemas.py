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

# The only language codes the API accepts.
Language = Literal["en", "hi", "bn"]
# Allowed widget-key format (used to check the key in the URL).
PUBLIC_KEY_REGEX = r"^pk_[A-Za-z0-9_-]{16,64}$"


# Parent for input models: unknown fields -> 422 error.
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields (e.g. a smuggled tenant_id)


# Body of POST /api/v1/bots.
class BotCreate(_Strict):
    # name: 1-100 characters, required.
    name: str = Field(min_length=1, max_length=100)
    # persona: up to 2000 characters, empty by default.
    persona: str = Field(default="", max_length=2000)
    # languages: 1 to 3 of en/hi/bn.
    languages: list[Language] = Field(min_length=1, max_length=3)
    # settings: free-form, {} by default.
    settings: dict[str, Any] = Field(default_factory=dict)


# Body of PATCH /api/v1/bots/{id}; at least one field required.
class BotUpdate(_Strict):
    """PATCH body: send only the fields to change."""

    # Each field is optional (None = not sent); limits match BotCreate.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    # Optional new persona.
    persona: str | None = Field(default=None, max_length=2000)
    # Optional new languages.
    languages: list[Language] | None = Field(default=None, min_length=1, max_length=3)
    # Optional new settings.
    settings: dict[str, Any] | None = None

    # A check that runs after all fields were read:
    @model_validator(mode="after")
    # the update must make sense as a whole.
    def _not_empty(self) -> "BotUpdate":
        # No fields sent at all...
        if not self.model_fields_set:
            # ...is an error (422).
            raise ValueError("send at least one field to change")
        # For each field that WAS sent...
        for name in self.model_fields_set:
            # ...sending null explicitly...
            if getattr(self, name) is None:
                # ...is also an error.
                raise ValueError(f"{name} cannot be null")
        # All good.
        return self


# What the API returns for a bot.
class BotOut(BaseModel):
    # The bot's id.
    id: UUID
    # Its name.
    name: str
    # Its persona.
    persona: str
    # Its languages.
    languages: list[str]
    # Its public widget key.
    public_key: str
    # Its extra settings.
    settings: dict[str, Any]


# ----------------------------------------------------------------- Bot Studio configuration
class PromptSettingsIn(_Strict):
    # persona: up to 1000 characters.
    persona: str = Field(default="", max_length=1000)
    # brand rules: up to 2000.
    brand_rules: str = Field(default="", max_length=2000)
    # custom instructions: up to 4000.
    custom_instructions: str = Field(default="", max_length=4000)
    # up to 20 banned topics, each at most 100 characters.
    banned_topics: list[Annotated[str, Field(max_length=100)]] = Field(
        default_factory=list, max_length=20
    )


# The model/style part of the request (unknown fields refused).
class GenerationSettingsIn(_Strict):
    # model key: default 'standard', lowercase letters/digits/dashes.
    model_key: str = Field(default="standard", pattern=r"^[a-z0-9-]{1,40}$")
    # style: one of the three presets.
    style: Literal["precise", "balanced", "friendly"] = "balanced"
    # manual temperature: 0-1, or none.
    temperature_override: float | None = Field(default=None, ge=0.0, le=1.0)
    # reply length: 64-2000 tokens.
    max_output_tokens: int = Field(default=600, ge=64, le=2000)


# The branding part of the request (unknown fields refused).
class BrandingIn(_Strict):
    # title: 1-60 characters, required.
    header_title: str = Field(min_length=1, max_length=60)
    # subtitle: up to 80.
    header_subtitle: str = Field(default="", max_length=80)
    # footer: up to 120.
    footer_text: str = Field(default="", max_length=120)
    # greeting: up to 300.
    greeting: str = Field(default="", max_length=300)
    # colour: #RRGGBB.
    primary_color: str = Field(default="#0F766E", pattern=r"^#[0-9A-Fa-f]{6}$")
    # launcher side: right or left.
    launcher_position: Literal["right", "left"] = "right"
    # logo id, or none.
    logo_asset_id: UUID | None = None


# Knowledge/retrieval settings (Phase 2). Ranges mirror RetrievalSettings (the domain decides).
class RetrievalSettingsIn(_Strict):
    # Chunk size in tokens (documents are re-processed when this changes on publish).
    chunk_size_tokens: int = Field(default=700, ge=200, le=1200)
    # Chunk overlap share (documents are re-processed when this changes on publish).
    chunk_overlap_ratio: float = Field(default=0.15, ge=0.0, le=0.3)
    # 'Same meaning' search size.
    vector_top_k: int = Field(default=20, ge=1, le=50)
    # 'Same words' search size.
    keyword_top_k: int = Field(default=20, ge=1, le=50)
    # Passages kept after reranking.
    rerank_top_n: int = Field(default=5, ge=1, le=10)
    # FAQ answer wins at or above this similarity.
    faq_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    # Below this reranker score the bot says "I'm not sure".
    confidence_threshold: float = Field(default=0.30, ge=0.0, le=1.0)


# Body for saving a configuration draft.
class BotConfigIn(_Strict):
    # Prompt part (defaults if not sent).
    prompt: PromptSettingsIn = Field(default_factory=PromptSettingsIn)
    # Generation part (defaults if not sent).
    generation: GenerationSettingsIn = Field(default_factory=GenerationSettingsIn)
    # Branding part (required).
    branding: BrandingIn
    # Retrieval part (defaults if not sent, so existing clients keep working).
    retrieval: RetrievalSettingsIn = Field(default_factory=RetrievalSettingsIn)


# What the API returns for a config version.
class BotConfigVersionOut(BaseModel):
    # The version number.
    version: int
    # Its status.
    status: Literal["draft", "published", "archived"]
    # Who saved it.
    created_by: str
    # When.
    created_at: datetime
    # The configuration itself.
    config: BotConfigIn


# One choosable model (no vendor model ids).
class ModelOptionOut(BaseModel):
    # The catalog key, e.g. 'standard'.
    key: str
    # The label to show.
    label: str


# 🔒 What the public widget gets: display fields only (R10).
class PublicWidgetConfigOut(BaseModel):
    """Public look of a widget only (R10): no prompts, model, plan or internal ids."""

    # Title.
    header_title: str
    # Subtitle.
    header_subtitle: str
    # Footer.
    footer_text: str
    # Greeting.
    greeting: str
    # Colour.
    primary_color: str
    # Launcher side.
    launcher_position: str
    # Logo address (none until logo uploads exist).
    logo_url: str | None
    # Languages.
    languages: list[str]
