"""Model catalog: the ONLY models tenants may choose from.

Tenants store a stable catalog key (e.g. "standard"), never a raw vendor model id. The platform
maps the key to provider + model id from configuration, so vendors and model versions can change
without touching any tenant's saved configuration.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict

from saathi.platform.errors import ConfigurationError, ValidationError

ALL_PLANS = frozenset({"starter", "growth", "pro"})


@dataclass(frozen=True, slots=True)
class ModelOption:
    key: str  # stable id stored in bot configs
    label: str  # what the Studio shows
    provider: str  # completion registry key, e.g. "anthropic"
    model_id: str  # vendor model id (from env)
    max_output_tokens: int
    plans: frozenset[str]


class ModelCatalog:
    def __init__(self, options: Iterable[ModelOption]) -> None:
        self._options: dict[str, ModelOption] = {}
        for option in options:
            if option.key in self._options:
                raise ConfigurationError(f"duplicate model catalog key '{option.key}'")
            self._options[option.key] = option

    def get(self, key: str) -> ModelOption:
        try:
            return self._options[key]
        except KeyError:
            raise ValidationError(f"unknown model '{key}'") from None

    def options_for_plan(self, plan: str) -> list[ModelOption]:
        return [o for o in self._options.values() if plan in o.plans]

    def is_allowed(self, key: str, plan: str) -> bool:
        option = self._options.get(key)
        return option is not None and plan in option.plans


class CatalogSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_model_small: str | None = None
    anthropic_model_large: str | None = None


def default_catalog(settings: CatalogSettings | None = None) -> ModelCatalog:
    """Options appear only when their model id is configured in the environment."""
    s = settings or CatalogSettings()
    options: list[ModelOption] = []
    if s.anthropic_model_small:
        options.append(
            ModelOption(
                key="standard",
                label="Standard - fast, lowest cost",
                provider="anthropic",
                model_id=s.anthropic_model_small,
                max_output_tokens=1000,
                plans=ALL_PLANS,
            )
        )
    if s.anthropic_model_large:
        options.append(
            ModelOption(
                key="advanced",
                label="Advanced - best answer quality",
                provider="anthropic",
                model_id=s.anthropic_model_large,
                max_output_tokens=2000,
                plans=frozenset({"growth", "pro"}),
            )
        )
    return ModelCatalog(options)
