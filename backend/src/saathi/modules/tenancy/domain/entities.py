# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The business objects 'Tenant' (a customer workspace) and 'Bot' (one chatbot), in plain
#       Python.
# Rules: A Bot checks its own rules when created (name length, languages...). It never changes
#        in place: methods like renamed() return a NEW Bot.
# Layer: domain/ = pure business logic, no web or database code (rule R3).
# ─────────────────────────────────────────────────────────────────────────────────────────────
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
# A customer workspace (a business using Saathi) and its plan.
class Tenant:
    id: UUID
    name: str
    plan: str
    monthly_token_cap: int


@dataclass(frozen=True, slots=True)
# One chatbot belonging to one tenant.
class Bot:
    id: UUID
    tenant_id: UUID
    name: str
    persona: str
    languages: tuple[str, ...]
    public_key: str  # identifies the bot to the widget; public, grants no admin access
    settings: Mapping[str, Any] = field(default_factory=dict)

    # Runs right after a Bot is created: reject invalid values immediately.
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

    # Return a copy with a new name (the original stays unchanged).
    def renamed(self, name: str) -> "Bot":
        return replace(self, name=name)

    # Return a copy with different languages.
    def with_languages(self, languages: tuple[str, ...]) -> "Bot":
        return replace(self, languages=languages)

    # Return a copy with a different persona text.
    def with_persona(self, persona: str) -> "Bot":
        return replace(self, persona=persona)

    # Return a copy with different extra settings.
    def with_settings(self, settings: Mapping[str, Any]) -> "Bot":
        return replace(self, settings=settings)
