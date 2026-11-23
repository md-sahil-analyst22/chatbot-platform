# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Our family of error types. Code raises these; api/errors.py turns them into HTTP
#       answers.
# Why: Business code doesn't know about HTTP - it just says 'not found' or 'conflict'. The API
#      layer picks the status code.
# Map: ValidationError 422 · NotFoundError 404 · ConflictError 409 · AuthenticationError 401 ·
#      AuthorizationError 403 · RateLimitError 429 · ProviderError 502/504 · others 500.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Error taxonomy. Domain code raises these; the API layer maps them to HTTP (api/errors.py).

No HTTP status codes here - the domain does not know it is served over HTTP.
"""


# Parent of all our errors. Every error has a short machine-readable `code` and a human
# `message`.
class SaathiError(Exception):
    # Default code; each child class sets its own.
    code: str = "internal_error"

    # Create the error with a message, and optionally a custom code.
    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        # Let Python's own Exception store the message too.
        super().__init__(message)
        # Keep the message (sent to the caller for 4xx errors).
        self.message = message
        # If a custom code was given...
        if code:
            # ...use it instead of the class default.
            self.code = code


# Errors about business rules.
class DomainError(SaathiError):
    # Code sent in the JSON error body.
    code = "domain_error"


# Input breaks a rule (e.g. bot name too long).
class ValidationError(DomainError):
    # Code sent in the JSON error body.
    code = "validation_error"


# Doesn't exist - or belongs to another tenant (we don't reveal which).
class NotFoundError(DomainError):
    # Code sent in the JSON error body.
    code = "not_found"


# Clashes with existing data, e.g. duplicate name or a publish race.
class ConflictError(DomainError):
    # Code sent in the JSON error body.
    code = "conflict"


# We don't know who you are (missing/invalid login).
class AuthenticationError(SaathiError):
    # Code sent in the JSON error body.
    code = "unauthenticated"


# We know who you are, but your role isn't allowed to do this.
class AuthorizationError(SaathiError):
    # Code sent in the JSON error body.
    code = "forbidden"


# 🔒 Someone tried to cross into another tenant's data.
class TenantIsolationError(SaathiError):
    """Raised when a request would cross tenant boundaries. Always logged as a security event."""

    # Shown as 'forbidden'; the HTTP answer is 404 so nothing is revealed.
    code = "forbidden"


# Too many requests.
class RateLimitError(SaathiError):
    # Code sent in the JSON error body.
    code = "rate_limited"


# An outside AI/vendor service failed.
class ProviderError(SaathiError):
    # Code sent in the JSON error body.
    code = "provider_error"


# An outside service was too slow.
class ProviderTimeoutError(ProviderError):
    # Code sent in the JSON error body.
    code = "provider_timeout"


# An outside service refused the request for good (bad key, unpaid billing, bad input): retrying
#   the same request won't help, so jobs fail at once instead of retrying.
class ProviderRejectedError(ProviderError):
    # Code sent in the JSON error body.
    code = "provider_rejected"


# Something on our side broke (database, encryption...).
class InfrastructureError(SaathiError):
    # Code sent in the JSON error body.
    code = "infrastructure_error"


# A setting is missing or wrong (e.g. no API key).
class ConfigurationError(InfrastructureError):
    # Code sent in the JSON error body.
    code = "configuration_error"
