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

# re — regular expressions (text patterns).
import re

# From collections.abc — standard type names for collections: Mapping = type for a read-only
#   dictionary.
from collections.abc import Mapping

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; field = per-field options such as a default empty list; replace
#   = copies an object with some fields changed.
from dataclasses import dataclass, field, replace

# From types — special built-in types: MappingProxyType = a read-only view of a dictionary.
from types import MappingProxyType

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# The languages a bot may speak: English, Hindi, Bengali.
SUPPORTED_LANGUAGES = frozenset({"en", "hi", "bn"})
# Longest allowed bot name.
MAX_NAME_LENGTH = 100
# Widget keys look like 'pk_' followed by 16-64 letters, digits, '_' or '-'.
PUBLIC_KEY_PATTERN = re.compile(r"pk_[A-Za-z0-9_-]{16,64}")


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# A customer workspace (a business using Saathi) and its plan.
class Tenant:
    # The workspace's id.
    id: UUID
    # The business name.
    name: str
    # Its plan: starter, growth or pro.
    plan: str
    # Most AI tokens the workspace may use per month.
    monthly_token_cap: int


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# One chatbot belonging to one tenant.
class Bot:
    # The bot's id.
    id: UUID
    # 🔒 The workspace that owns it.
    tenant_id: UUID
    # Its display name.
    name: str
    # Its personality text.
    persona: str
    # The languages it speaks, e.g. ('en', 'hi').
    languages: tuple[str, ...]
    public_key: str  # identifies the bot to the widget; public, grants no admin access
    # Extra free-form settings (empty by default).
    settings: Mapping[str, Any] = field(default_factory=dict)

    # Runs right after a Bot is created: reject invalid values immediately.
    def __post_init__(self) -> None:
        # The widget key must have the right format...
        if not PUBLIC_KEY_PATTERN.fullmatch(self.public_key):
            # ...otherwise refuse.
            raise ValidationError("invalid bot public key")
        # The name must not be blank...
        if not self.name.strip():
            # ...otherwise refuse.
            raise ValidationError("bot name must not be empty")
        # The name must not be too long...
        if len(self.name) > MAX_NAME_LENGTH:
            # ...otherwise refuse.
            raise ValidationError("bot name is too long")
        # At least one language is required...
        if not self.languages:
            # ...otherwise refuse.
            raise ValidationError("bot needs at least one language")
        # Languages we don't support (set difference).
        unknown = set(self.languages) - SUPPORTED_LANGUAGES
        # If there are any...
        if unknown:
            # ...refuse and name them.
            raise ValidationError(f"unsupported languages: {sorted(unknown)}")
        # Read-only view (shallow): callers cannot mutate settings behind the entity's back.
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))

    # Return a copy with a new name (the original stays unchanged).
    def renamed(self, name: str) -> "Bot":
        # A copy with only the name changed.
        return replace(self, name=name)

    # Return a copy with different languages.
    def with_languages(self, languages: tuple[str, ...]) -> "Bot":
        # A copy with only the languages changed.
        return replace(self, languages=languages)

    # Return a copy with a different persona text.
    def with_persona(self, persona: str) -> "Bot":
        # A copy with only the persona changed.
        return replace(self, persona=persona)

    # Return a copy with different extra settings.
    def with_settings(self, settings: Mapping[str, Any]) -> "Bot":
        # A copy with only the settings changed (re-checked by __post_init__).
        return replace(self, settings=settings)
