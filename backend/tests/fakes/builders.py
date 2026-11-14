"""Small builders so tests read like the domain."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from saathi.modules.tenancy.domain.bot_config import (
    BotConfig,
    Branding,
    GenerationSettings,
    PromptSettings,
)
from saathi.modules.tenancy.domain.entities import Bot
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
