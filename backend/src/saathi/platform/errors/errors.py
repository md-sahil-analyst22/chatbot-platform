"""Error taxonomy. Domain code raises these; the API layer maps them to HTTP (api/errors.py).

No HTTP status codes here - the domain does not know it is served over HTTP.
"""


class SaathiError(Exception):
    code: str = "internal_error"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class DomainError(SaathiError):
    code = "domain_error"


class ValidationError(DomainError):
    code = "validation_error"


class NotFoundError(DomainError):
    code = "not_found"


class ConflictError(DomainError):
    code = "conflict"


class AuthenticationError(SaathiError):
    code = "unauthenticated"


class AuthorizationError(SaathiError):
    code = "forbidden"


class TenantIsolationError(SaathiError):
    """Raised when a request would cross tenant boundaries. Always logged as a security event."""

    code = "forbidden"


class RateLimitError(SaathiError):
    code = "rate_limited"


class ProviderError(SaathiError):
    code = "provider_error"


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"


class InfrastructureError(SaathiError):
    code = "infrastructure_error"


class ConfigurationError(InfrastructureError):
    code = "configuration_error"
