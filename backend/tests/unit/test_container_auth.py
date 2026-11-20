# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 Production refuses to start without login settings.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""build_token_verifier (ADR-0007): deployed environments refuse to start without auth."""

import httpx
import pytest

from saathi.bootstrap.container import build_token_verifier
from saathi.platform.config.settings import Settings
from saathi.platform.errors import ConfigurationError
from saathi.platform.security.jwt_verifier import JwksTokenVerifier

AUTH = {
    "auth_jwks_url": "https://p.supabase.co/auth/v1/.well-known/jwks.json",
    "auth_issuer": "https://p.supabase.co/auth/v1",
    "auth_audience": "authenticated",
}


def _settings(env: str, **auth: str | None) -> Settings:
    return Settings(env=env, **auth)  # type: ignore[arg-type]  # DB/Redis URLs come from conftest


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize("missing", ["auth_jwks_url", "auth_issuer", "auth_audience"])
def test_deployed_env_without_auth_refuses_to_start(env: str, missing: str) -> None:
    with pytest.raises(ConfigurationError, match="AUTH_"):
        build_token_verifier(_settings(env, **{**AUTH, missing: None}), httpx.AsyncClient(), None)  # type: ignore[arg-type]


@pytest.mark.parametrize("env", ["local", "test"])
def test_local_without_auth_has_no_verifier(env: str) -> None:
    assert build_token_verifier(_settings(env), httpx.AsyncClient(), None) is None  # type: ignore[arg-type]


def test_configured_auth_builds_jwks_verifier() -> None:
    verifier = build_token_verifier(_settings("production", **AUTH), httpx.AsyncClient(), None)  # type: ignore[arg-type]
    assert isinstance(verifier, JwksTokenVerifier)
