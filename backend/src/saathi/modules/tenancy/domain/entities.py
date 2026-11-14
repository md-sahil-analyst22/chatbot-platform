"""Tenancy domain. Pure Python: no FastAPI, SQLAlchemy, pydantic or vendor SDKs.

Bot is immutable: every change returns a new, re-validated Bot, so an invalid Bot can never
exist in memory.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any
from uuid import UUID

from saathi.platform.errors import ValidationError

SUPPORTED_LANGUAGES = frozenset({"en", "hi", "bn"})
MAX_NAME_LENGTH = 100
PUBLIC_KEY_PATTERN = re.compile(r"pk_[A-Za-z0-9_-]{16,64}")


@dataclass(frozen=True, slots=True)
class Tenant:
    id: UUID
    name: str
    plan: str
    monthly_token_cap: int


@dataclass(frozen=True, slots=True)
class Bot:
    id: UUID
    tenant_id: UUID
    name: str
    persona: str
    languages: tuple[str, ...]
    public_key: str  # identifies the bot to the widget; public, grants no admin access
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not PUBLIC_KEY_PATTERN.fullmatch(self.public_key):
            raise ValidationError("invalid bot public key")
        if not self.name.strip():
            raise ValidationError("bot name must not be empty")
        if len(self.name) > MAX_NAME_LENGTH:
            raise ValidationError("bot name is too long")
        if not self.languages:
            raise ValidationError("bot needs at least one language")
        unknown = set(self.languages) - SUPPORTED_LANGUAGES
        if unknown:
            raise ValidationError(f"unsupported languages: {sorted(unknown)}")
        # Read-only view (shallow): callers cannot mutate settings behind the entity's back.
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))

    def renamed(self, name: str) -> "Bot":
        return replace(self, name=name)

    def with_languages(self, languages: tuple[str, ...]) -> "Bot":
        return replace(self, languages=languages)
