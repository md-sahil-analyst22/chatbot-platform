# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The list of AI models a tenant may choose for a bot, and which plan may use which.
# Why: Bots store a short key like 'standard', never a vendor's model name. We can switch models
#      later without touching any saved bot.
# Used by: Bot configuration (model must be on the tenant's plan) and the /model-options
#          endpoint.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Model catalog: the ONLY models tenants may choose from.

Tenants store a stable catalog key (e.g. "standard"), never a raw vendor model id. The platform
maps the key to provider + model id from configuration, so vendors and model versions can change
without touching any tenant's saved configuration.
"""

# From collections.abc — standard type names for collections: Iterable = type for anything you
#   can loop over.
from collections.abc import Iterable

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From pydantic_settings — reads settings from environment variables and .env: BaseSettings =
#   parent class for a group of settings; SettingsConfigDict = where settings are read from (.env,
#   prefix).
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ConfigurationError, ValidationError

# Every plan name. 'standard' is on all plans; 'advanced' only on growth and pro.
ALL_PLANS = frozenset({"starter", "growth", "pro"})


@dataclass(frozen=True, slots=True)
# One choosable model. frozen=True means it can't be changed after creation.
class ModelOption:
    key: str  # stable id stored in bot configs
    label: str  # what the Studio shows
    provider: str  # completion registry key, e.g. "anthropic"
    model_id: str  # vendor model id (from env)
    max_output_tokens: int
    plans: frozenset[str]


# The collection of options, looked up by key.
class ModelCatalog:
    def __init__(self, options: Iterable[ModelOption]) -> None:
        self._options: dict[str, ModelOption] = {}
        for option in options:
            if option.key in self._options:
                raise ConfigurationError(f"duplicate model catalog key '{option.key}'")
            self._options[option.key] = option

    # Find a model by key; an unknown key is a validation error (422).
    def get(self, key: str) -> ModelOption:
        try:
            return self._options[key]
        except KeyError:
            raise ValidationError(f"unknown model '{key}'") from None

    # Only the models a given plan may use.
    def options_for_plan(self, plan: str) -> list[ModelOption]:
        return [o for o in self._options.values() if plan in o.plans]

    # 'May this plan use this model?' - True/False.
    def is_allowed(self, key: str, plan: str) -> bool:
        option = self._options.get(key)
        return option is not None and plan in option.plans


# Reads the real model ids from .env (e.g. GEMINI_MODEL_SMALL=gemini-3.8-flash).
class CatalogSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_model_small: str | None = None
    gemini_model_large: str | None = None
    anthropic_model_small: str | None = None
    anthropic_model_large: str | None = None


# Builds the catalog. A model only appears if its id is configured in .env.
def default_catalog(settings: CatalogSettings | None = None) -> ModelCatalog:
    """Options appear only when their model id is configured in the environment.

    Gemini is the primary vendor (ADR-0006), so it owns the plain "standard"/"advanced" keys.
    Other vendors get prefixed keys, so adding or removing one never changes a saved config.
    """
    s = settings or CatalogSettings()
    paid = frozenset({"growth", "pro"})
    options: list[ModelOption] = []

    # Small helper: add one option, but only when its model id is set.
    def add(
        key: str,
        label: str,
        provider: str,
        model_id: str | None,
        max_tokens: int,
        plans: frozenset[str],
    ) -> None:
        if model_id:
            options.append(ModelOption(key, label, provider, model_id, max_tokens, plans))

    add("standard", "Standard - fast, lowest cost", "gemini", s.gemini_model_small, 1000, ALL_PLANS)
    add("advanced", "Advanced - best answer quality", "gemini", s.gemini_model_large, 2000, paid)
    add(
        "claude-standard",
        "Claude Standard - fast",
        "anthropic",
        s.anthropic_model_small,
        1000,
        ALL_PLANS,
    )
    add(
        "claude-advanced",
        "Claude Advanced - best quality",
        "anthropic",
        s.anthropic_model_large,
        2000,
        paid,
    )
    return ModelCatalog(options)
