"""Maps the internal error taxonomy to a stable API error model. Never leaks stack traces."""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from saathi.platform.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    SaathiError,
    TenantIsolationError,
    ValidationError,
)

log = structlog.get_logger()

_STATUS: list[tuple[type[SaathiError], int]] = [
    (ValidationError, 422),
    (NotFoundError, 404),
    (ConflictError, 409),
    (AuthenticationError, 401),
    (TenantIsolationError, 404),  # don't reveal that another tenant's object exists
    (AuthorizationError, 403),
    (RateLimitError, 429),
    (ProviderTimeoutError, 504),
    (ProviderError, 502),
]


def _status_for(exc: SaathiError) -> int:
    for typ, status in _STATUS:
        if isinstance(exc, typ):
            return status
    return 500


def _body(
    request: Request, code: str, message: str, details: list[dict[str, object]] | None = None
) -> dict[str, object]:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SaathiError)
    async def handle_saathi_error(request: Request, exc: SaathiError) -> JSONResponse:
        status = _status_for(exc)
        if isinstance(exc, TenantIsolationError):
            log.warning("security.tenant_isolation_violation", path=request.url.path)
        message = exc.message if status < 500 else "An internal error occurred."
        return JSONResponse(status_code=status, content=_body(request, exc.code, message))

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Field locations and error types only - never echo submitted values (may contain PII).
        details: list[dict[str, object]] = [
            {"loc": list(e.get("loc", ())), "type": e.get("type")} for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body(request, "validation_error", "Request validation failed.", details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500, content=_body(request, "internal_error", "An internal error occurred.")
        )
