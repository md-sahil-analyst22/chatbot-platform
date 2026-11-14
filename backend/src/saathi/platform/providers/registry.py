"""Generic provider registry: Interface -> Registry -> Factory -> Adapter.

Each port (LLM, Embedder, Reranker, STT ...) owns one registry. Adapters register themselves
by name; the container picks one by config key. Adding a vendor = new adapter + register.
"""

from collections.abc import Callable
from typing import Any

from saathi.platform.errors import ConfigurationError


class ProviderRegistry[T]:
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register[F: Callable[..., Any]](self, name: str) -> Callable[[F], F]:
        def decorator(factory: F) -> F:
            if name in self._factories:
                raise ConfigurationError(f"{self._kind} provider '{name}' already registered")
            self._factories[name] = factory
            return factory

        return decorator

    def create(self, name: str, **kwargs: Any) -> T:
        try:
            factory = self._factories[name]
        except KeyError:
            available = ", ".join(sorted(self._factories)) or "none"
            raise ConfigurationError(
                f"unknown {self._kind} provider '{name}' (available: {available})"
            ) from None
        return factory(**kwargs)

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
