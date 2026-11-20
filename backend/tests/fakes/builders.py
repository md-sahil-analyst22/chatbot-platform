# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Small helpers to build test objects (bots, configs, callers) in one line.
# How to run: Used automatically by the tests; nothing to run directly.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Small builders so tests read like the domain."""

# From datetime — dates and times: UTC = the UTC time zone; datetime = a date + time value.
from datetime import UTC, datetime

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfig = one full configuration; Branding = how the widget looks; GenerationSettings =
#   model and answer style; PromptSettings = the tenant's instructions.
from saathi.modules.tenancy.domain.bot_config import (
    BotConfig,
    Branding,
    GenerationSettings,
    PromptSettings,
)

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   ALL_PLANS = every plan name; ModelCatalog = the catalog; ModelOption = one choosable model.
from saathi.platform.config.model_catalog import ALL_PLANS, ModelCatalog, ModelOption


# Build a valid test bot (random ids; optional tenant and name).
def make_bot(tenant_id: UUID | None = None, name: str = "Mitra") -> Bot:
    # A Bot with:
    return Bot(
        # a random id,
        id=uuid4(),
        # the given tenant, or a random one,
        tenant_id=tenant_id or uuid4(),
        # the name,
        name=name,
        # no persona,
        persona="",
        # English only,
        languages=("en",),
        # a random valid widget key.
        public_key="pk_" + uuid4().hex,
    )


# Build a valid test configuration.
def make_config(model_key: str = "standard", title: str = "TaxMitra") -> BotConfig:
    # A BotConfig with:
    return BotConfig(
        # a persona,
        prompt=PromptSettings(persona="Polite and precise"),
        # the chosen model key,
        generation=GenerationSettings(model_key=model_key),
        # a title and a footer.
        branding=Branding(header_title=title, footer_text="Powered by Saathi"),
    )


# Build a small catalog with two test models.
def make_catalog() -> ModelCatalog:
    # A catalog of:
    return ModelCatalog(
        # these options:
        [
            # 'standard', allowed on every plan,
            ModelOption("standard", "Standard", "anthropic", "small-model", 1000, ALL_PLANS),
            # 'advanced', allowed only on 'pro'.
            ModelOption(
                "advanced", "Advanced", "anthropic", "large-model", 2000, frozenset({"pro"})
            ),
        ]
    )


# A fixed moment in time, so tests are repeatable.
NOW = datetime(2026, 11, 12, tzinfo=UTC)
