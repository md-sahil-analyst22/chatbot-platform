# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Vendor HTTP error statuses are sorted into 'retry later' (408, 429, 5xx) and
#                'refused for good' (other 4xx), so jobs never retry a request that can't succeed.
# How to run: cd backend && uv run pytest tests/unit/test_provider_errors.py (no network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""platform/http/provider_errors.py."""

# httpx — builds fake responses and the status error that wraps them.
import httpx

# pytest — the test framework.
import pytest

# From saathi.platform.errors — ProviderError = retryable; ProviderRejectedError = permanent.
from saathi.platform.errors import ProviderError, ProviderRejectedError

# From saathi.platform.http.provider_errors — provider_http_error = status -> error type.
from saathi.platform.http.provider_errors import provider_http_error


# The status error httpx raises for a response with this code.
def _status_error(status: int) -> httpx.HTTPStatusError:
    # A request...
    request = httpx.Request("POST", "https://vendor.example/v1")
    # ...answered with that status.
    response = httpx.Response(status, request=request)
    # The error raise_for_status() would raise.
    return httpx.HTTPStatusError("error", request=request, response=response)


# Each pair: (status, is it permanent?).
@pytest.mark.parametrize(
    ("status", "permanent"),
    [
        # Bad request, bad key, forbidden/unpaid billing, unknown model: permanent.
        (400, True),
        (401, True),
        (403, True),
        (404, True),
        # Request timeout and rate limit: temporary.
        (408, False),
        (429, False),
        # Server errors: temporary.
        (500, False),
        (503, False),
    ],
)
# Permanent refusals and temporary failures are told apart.
def test_status_classification(status: int, permanent: bool) -> None:
    # Classify it.
    err = provider_http_error(_status_error(status), "embedding provider failed")
    # Always a provider error (callers that catch ProviderError keep working)...
    assert isinstance(err, ProviderError)
    # ...the 'refused for good' kind only for permanent statuses.
    assert isinstance(err, ProviderRejectedError) is permanent
    # The message names the status, never the vendor's body.
    assert err.message == f"embedding provider failed (HTTP {status})"
