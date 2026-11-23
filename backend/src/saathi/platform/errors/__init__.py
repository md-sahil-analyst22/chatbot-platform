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
    ProviderRejectedError,
    ProviderTimeoutError,
    RateLimitError,
    SaathiError,
    TenantIsolationError,
    ValidationError,
)

# __all__ = the names other files may import from this package.
__all__ = [
    # AuthenticationError: 401 not logged in.
    "AuthenticationError",
    # AuthorizationError: 403 role not allowed.
    "AuthorizationError",
    # ConfigurationError: a setting is missing.
    "ConfigurationError",
    # ConflictError: 409 clash with existing data.
    "ConflictError",
    # DomainError: business-rule error.
    "DomainError",
    # InfrastructureError: our side broke.
    "InfrastructureError",
    # NotFoundError: 404 not found.
    "NotFoundError",
    # ProviderError: a vendor failed.
    "ProviderError",
    "ProviderRejectedError",
    # ProviderTimeoutError: a vendor was too slow.
    "ProviderTimeoutError",
    # RateLimitError: 429 too many requests.
    "RateLimitError",
    # SaathiError: parent of all our errors.
    "SaathiError",
    # TenantIsolationError: tried to cross tenants.
    "TenantIsolationError",
    # ValidationError: 422 invalid input.
    "ValidationError",
]
