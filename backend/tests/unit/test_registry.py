import pytest

from saathi.platform.errors import ConfigurationError
from saathi.platform.providers import ProviderRegistry


def test_register_and_create() -> None:
    reg: ProviderRegistry[str] = ProviderRegistry("demo")

    @reg.register("echo")
    def make(value: str) -> str:
        return value

    assert reg.create("echo", value="hi") == "hi"
    assert reg.available() == ("echo",)


def test_unknown_provider_lists_available() -> None:
    reg: ProviderRegistry[str] = ProviderRegistry("demo")
    with pytest.raises(ConfigurationError, match="available: none"):
        reg.create("missing")


def test_duplicate_registration_rejected() -> None:
    reg: ProviderRegistry[str] = ProviderRegistry("demo")
    reg.register("a")(lambda: "x")
    with pytest.raises(ConfigurationError):
        reg.register("a")(lambda: "y")
