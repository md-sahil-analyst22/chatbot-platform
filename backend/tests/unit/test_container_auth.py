# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 Production refuses to start without login settings.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""build_token_verifier (ADR-0007): deployed environments refuse to start without auth."""

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From saathi.bootstrap.container — builds the app's shared objects once at start-up:
#   build_token_verifier = creates the login checker (production refuses to start without one).
from saathi.bootstrap.container import build_token_verifier

# From saathi.platform.config.settings — the app's core settings: Settings = the settings class.
from saathi.platform.config.settings import Settings

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing.
from saathi.platform.errors import ConfigurationError

# From saathi.platform.security.jwt_verifier — the login-token checker: JwksTokenVerifier = the
#   real login checker.
from saathi.platform.security.jwt_verifier import JwksTokenVerifier

# Valid-looking login settings for the tests:
AUTH = {
    # where the public keys are published,
    "auth_jwks_url": "https://p.supabase.co/auth/v1/.well-known/jwks.json",
    # the issuer,
    "auth_issuer": "https://p.supabase.co/auth/v1",
    # the audience.
    "auth_audience": "authenticated",
}


# Helper: settings for a given environment, plus any login settings.
def _settings(env: str, **auth: str | None) -> Settings:
    return Settings(env=env, **auth)  # type: ignore[arg-type]  # DB/Redis URLs come from conftest


# Run for both deployed environments...
@pytest.mark.parametrize("env", ["staging", "production"])
# ...and for each of the three login settings being missing (6 runs in total).
@pytest.mark.parametrize("missing", ["auth_jwks_url", "auth_issuer", "auth_audience"])
# 🔒 A deployed server with any login setting missing refuses to start.
def test_deployed_env_without_auth_refuses_to_start(env: str, missing: str) -> None:
    # Expect a ConfigurationError mentioning AUTH_ from the next line:
    with pytest.raises(ConfigurationError, match="AUTH_"):
        build_token_verifier(_settings(env, **{**AUTH, missing: None}), httpx.AsyncClient(), None)  # type: ignore[arg-type]


# Run for both local environments.
@pytest.mark.parametrize("env", ["local", "test"])
# Locally, missing login settings are allowed: there's just no checker (every call refused).
def test_local_without_auth_has_no_verifier(env: str) -> None:
    assert build_token_verifier(_settings(env), httpx.AsyncClient(), None) is None  # type: ignore[arg-type]


# All login settings present -> the real JWKS checker is built.
def test_configured_auth_builds_jwks_verifier() -> None:
    verifier = build_token_verifier(_settings("production", **AUTH), httpx.AsyncClient(), None)  # type: ignore[arg-type]
    # It's the JWKS checker.
    assert isinstance(verifier, JwksTokenVerifier)
