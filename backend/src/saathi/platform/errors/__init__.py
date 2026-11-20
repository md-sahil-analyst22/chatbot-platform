# From saathi.platform.errors.errors — our error types: AuthenticationError = 401 not logged in;
#   AuthorizationError = 403 role not allowed; ConfigurationError = a setting is missing;
#   ConflictError = 409 clash with existing data; DomainError = business-rule error;
#   InfrastructureError = our side broke; NotFoundError = 404 not found; ProviderError = a vendor
#   failed; ProviderTimeoutError = a vendor was too slow; RateLimitError = 429 too many requests;
#   SaathiError = parent of all our errors; TenantIsolationError = tried to cross tenants;
#   ValidationError = 422 invalid input.
from saathi.platform.errors.errors import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    DomainError,
    InfrastructureError,
    NotFoundError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    SaathiError,
    TenantIsolationError,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "ConflictError",
    "DomainError",
    "InfrastructureError",
    "NotFoundError",
    "ProviderError",
    "ProviderTimeoutError",
    "RateLimitError",
    "SaathiError",
    "TenantIsolationError",
    "ValidationError",
]
