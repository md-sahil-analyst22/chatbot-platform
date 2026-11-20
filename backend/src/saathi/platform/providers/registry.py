# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: A generic 'phone book' of vendor adapters.
# How: An adapter registers itself under a name (e.g. 'gemini'). Later the app asks the registry
#      to create the one named in settings.
# Why: New vendors are added by adding a file, without changing business code (open/closed
#      principle).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Generic provider registry: Interface -> Registry -> Factory -> Adapter.

Each port (LLM, Embedder, Reranker, STT ...) owns one registry. Adapters register themselves
by name; the container picks one by config key. Adding a vendor = new adapter + register.
"""

# From collections.abc — standard type names for collections: Callable = type for a function.
from collections.abc import Callable

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing.
from saathi.platform.errors import ConfigurationError


# One registry per kind of vendor (LLM, embedder, reranker, speech, storage...). [T] = the kind
# it holds.
class ProviderRegistry[T]:
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    # Used as `@registry.register("name")` above an adapter's factory function.
    def register[F: Callable[..., Any]](self, name: str) -> Callable[[F], F]:
        def decorator(factory: F) -> F:
            # Two adapters with the same name would be a bug - fail loudly at start-up.
            if name in self._factories:
                raise ConfigurationError(f"{self._kind} provider '{name}' already registered")
            self._factories[name] = factory
            return factory

        return decorator

    # Build the adapter registered under `name`. Unknown name -> clear error listing what IS
    # available.
    def create(self, name: str, **kwargs: Any) -> T:
        try:
            factory = self._factories[name]
        except KeyError:
            available = ", ".join(sorted(self._factories)) or "none"
            raise ConfigurationError(
                f"unknown {self._kind} provider '{name}' (available: {available})"
            ) from None
        return factory(**kwargs)

    # The registered names (used by tests).
    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
