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


# @dataclass writes __init__ for us; frozen=True makes objects unchangeable.
@dataclass(frozen=True, slots=True)
# One choosable model. frozen=True means it can't be changed after creation.
class ModelOption:
    key: str  # stable id stored in bot configs
    label: str  # what the Studio shows
    provider: str  # completion registry key, e.g. "anthropic"
    model_id: str  # vendor model id (from env)
    # The longest reply (in tokens) this model may write.
    max_output_tokens: int
    # Which plans may use this model.
    plans: frozenset[str]


# The collection of options, looked up by key.
class ModelCatalog:
    # Build the catalog from a list of options.
    def __init__(self, options: Iterable[ModelOption]) -> None:
        # An empty dictionary: key -> option.
        self._options: dict[str, ModelOption] = {}
        # Go through every option...
        for option in options:
            # ...if its key is already taken...
            if option.key in self._options:
                # ...stop at start-up: two models with one key would be a configuration bug.
                raise ConfigurationError(f"duplicate model catalog key '{option.key}'")
            # Otherwise store it under its key.
            self._options[option.key] = option

    # Find a model by key; an unknown key is a validation error (422).
    def get(self, key: str) -> ModelOption:
        # Try to look the key up...
        try:
            # ...and return the option if found.
            return self._options[key]
        # Key not in the dictionary:
        except KeyError:
            # answer 422 'unknown model' (`from None` hides the internal KeyError).
            raise ValidationError(f"unknown model '{key}'") from None

    # Only the models a given plan may use.
    def options_for_plan(self, plan: str) -> list[ModelOption]:
        # Keep only the options whose `plans` include this plan.
        return [o for o in self._options.values() if plan in o.plans]

    # 'May this plan use this model?' - True/False.
    def is_allowed(self, key: str, plan: str) -> bool:
        # Find the option (None if the key is unknown).
        option = self._options.get(key)
        # Allowed only if it exists AND this plan is in its plans.
        return option is not None and plan in option.plans


# Reads the real model ids from .env (e.g. GEMINI_MODEL_SMALL=gemini-3.8-flash).
class CatalogSettings(BaseSettings):
    # Read from .env and ignore unrelated variables.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # GEMINI_MODEL_SMALL: the fast, cheap Gemini model id.
    gemini_model_small: str | None = None
    # GEMINI_MODEL_LARGE: the higher-quality Gemini model id.
    gemini_model_large: str | None = None
    # ANTHROPIC_MODEL_SMALL: the fast Claude model id.
    anthropic_model_small: str | None = None
    # ANTHROPIC_MODEL_LARGE: the higher-quality Claude model id.
    anthropic_model_large: str | None = None


# Builds the catalog. A model only appears if its id is configured in .env.
def default_catalog(settings: CatalogSettings | None = None) -> ModelCatalog:
    """Options appear only when their model id is configured in the environment.

    Gemini is the primary vendor (ADR-0006), so it owns the plain "standard"/"advanced" keys.
    Other vendors get prefixed keys, so adding or removing one never changes a saved config.
    """
    # Use the settings passed in (tests do this) or read them from .env.
    s = settings or CatalogSettings()
    # The paid plans.
    paid = frozenset({"growth", "pro"})
    # The list we fill below.
    options: list[ModelOption] = []

    # Small helper: add one option, but only when its model id is set.
    def add(
        # the stable key saved in bot configs,
        key: str,
        # the label shown in Bot Studio,
        label: str,
        # the vendor name,
        provider: str,
        # the vendor's model id (None/empty = not configured),
        model_id: str | None,
        # the reply length limit,
        max_tokens: int,
        # which plans may use it.
        plans: frozenset[str],
    ) -> None:
        # Only add the model if its id is configured...
        if model_id:
            # ...then append it to the list.
            options.append(ModelOption(key, label, provider, model_id, max_tokens, plans))

    # 'standard': Gemini small model, every plan, up to 1000 tokens.
    add("standard", "Standard - fast, lowest cost", "gemini", s.gemini_model_small, 1000, ALL_PLANS)
    # 'advanced': Gemini large model, paid plans only, up to 2000 tokens.
    add("advanced", "Advanced - best answer quality", "gemini", s.gemini_model_large, 2000, paid)
    # 'claude-standard': Claude small model, every plan.
    add(
        "claude-standard",
        "Claude Standard - fast",
        "anthropic",
        s.anthropic_model_small,
        1000,
        ALL_PLANS,
    )
    # 'claude-advanced': Claude large model, paid plans only.
    add(
        "claude-advanced",
        "Claude Advanced - best quality",
        "anthropic",
        s.anthropic_model_large,
        2000,
        paid,
    )
    # Wrap the list in a ModelCatalog.
    return ModelCatalog(options)
