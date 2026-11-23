# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Turns a vendor's HTTP error status into the right error type, so callers know whether
#       trying again can help.
#   Temporary (retry later): 408 timeout, 429 too many requests, every 5xx server error.
#   Permanent (don't retry): other 4xx, e.g. 401 bad key, 403 unpaid billing / no permission,
#   400 bad request, 404 unknown model.
# Why: CLAUDE.md 'Resilience': retry only transient failures. Retrying a 403 five times wastes
#      time and hides the real problem from the operator.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Classify vendor HTTP errors into retryable and permanent provider errors."""

# httpx — the HTTP client (its HTTPStatusError carries the response).
import httpx

# From saathi.platform.errors — our error types: ProviderError = a vendor failed (may be
#   temporary); ProviderRejectedError = the vendor refused for good.
from saathi.platform.errors import ProviderError, ProviderRejectedError

# 4xx statuses that are temporary: request timeout, too many requests.
_TEMPORARY_4XX = frozenset({408, 429})


# The right error for a vendor's error status.
def provider_http_error(exc: httpx.HTTPStatusError, message: str) -> ProviderError:
    """Permanent 4xx -> ProviderRejectedError; 408/429/5xx -> ProviderError (retryable).

    The message gets the status code only (never the vendor's body, which can echo request data).
    """
    # The HTTP status the vendor answered with.
    status = exc.response.status_code
    # A client error that won't change on retry.
    if 400 <= status < 500 and status not in _TEMPORARY_4XX:
        # Permanent.
        return ProviderRejectedError(f"{message} (HTTP {status})")
    # Temporary (or unknown): retryable.
    return ProviderError(f"{message} (HTTP {status})")
