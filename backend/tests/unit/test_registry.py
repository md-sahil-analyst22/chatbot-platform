# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The vendor registry: register, create, duplicates and unknown names.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# pytest — the test framework.
import pytest

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing.
from saathi.platform.errors import ConfigurationError

# From saathi.platform.providers — the vendor registry: ProviderRegistry = the 'phone book' of
#   vendor adapters.
from saathi.platform.providers import ProviderRegistry


# Registering an adapter and creating it by name works.
def test_register_and_create() -> None:
    # A fresh registry for this test.
    reg: ProviderRegistry[str] = ProviderRegistry("demo")

    # Register the function below under the name 'echo'.
    @reg.register("echo")
    # A tiny factory that returns what it is given.
    def make(value: str) -> str:
        # Return it.
        return value

    # Creating 'echo' calls the factory with the arguments.
    assert reg.create("echo", value="hi") == "hi"
    # The registry lists 'echo'.
    assert reg.available() == ("echo",)


# Asking for an unknown name gives a helpful error.
def test_unknown_provider_lists_available() -> None:
    # A fresh, empty registry.
    reg: ProviderRegistry[str] = ProviderRegistry("demo")
    # Expect a ConfigurationError whose message says 'available: none'...
    with pytest.raises(ConfigurationError, match="available: none"):
        # ...when asking for a name that was never registered.
        reg.create("missing")


# Registering the same name twice is refused.
def test_duplicate_registration_rejected() -> None:
    # A fresh registry.
    reg: ProviderRegistry[str] = ProviderRegistry("demo")
    # Register 'a' once.
    reg.register("a")(lambda: "x")
    # Expect an error...
    with pytest.raises(ConfigurationError):
        # ...when registering 'a' again.
        reg.register("a")(lambda: "y")
