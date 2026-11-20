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


def make_bot(tenant_id: UUID | None = None, name: str = "Mitra") -> Bot:
    return Bot(
        id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        name=name,
        persona="",
        languages=("en",),
        public_key="pk_" + uuid4().hex,
    )


def make_config(model_key: str = "standard", title: str = "TaxMitra") -> BotConfig:
    return BotConfig(
        prompt=PromptSettings(persona="Polite and precise"),
        generation=GenerationSettings(model_key=model_key),
        branding=Branding(header_title=title, footer_text="Powered by Saathi"),
    )


def make_catalog() -> ModelCatalog:
    return ModelCatalog(
        [
            ModelOption("standard", "Standard", "anthropic", "small-model", 1000, ALL_PLANS),
            ModelOption(
                "advanced", "Advanced", "anthropic", "large-model", 2000, frozenset({"pro"})
            ),
        ]
    )


NOW = datetime(2026, 11, 12, tzinfo=UTC)
