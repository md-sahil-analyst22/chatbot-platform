# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Turns every kind of error into ONE standard JSON answer: {"error": {code, message,
#       request_id}}.
# Why: Clients (Bot Studio, the widget) only need to understand one error shape, and internal
#      details never leak.
# Security: 🔒 Server errors (500) always say just 'An internal error occurred.' Validation
#           errors list WHICH field failed, never the value sent (it may be personal data).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Maps the internal error taxonomy to a stable API error model. Never leaks stack traces."""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

# Which of our error types becomes which HTTP status code. Order matters: the first match wins.
_STATUS: list[tuple[type[SaathiError], int]] = [
    (ValidationError, 422),
    (NotFoundError, 404),
    (ConflictError, 409),
    (AuthenticationError, 401),
    # 🔒 Another tenant's data answers 404 'not found', so nobody can even learn it exists.
    (TenantIsolationError, 404),  # don't reveal that another tenant's object exists
    (AuthorizationError, 403),
    (RateLimitError, 429),
    (ProviderTimeoutError, 504),
    (ProviderError, 502),
]


# Look up the HTTP status for an error; anything unknown is a 500.
def _status_for(exc: SaathiError) -> int:
    for typ, status in _STATUS:
        if isinstance(exc, typ):
            return status
    return 500


# Build the standard error JSON, including the request id so a user can quote it when reporting
# a problem.
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


# Framework-raised HTTP errors (unknown route, wrong method, ...) mapped to our codes, with fixed
# messages so nothing raised by a library is echoed back to the client.
# Fixed codes and messages for errors raised by the web framework itself (unknown URL, wrong
# method...).
_HTTP_CODES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Bad request."),
    401: ("unauthenticated", "Authentication required."),
    403: ("forbidden", "Forbidden."),
    404: ("not_found", "Not found."),
    405: ("method_not_allowed", "Method not allowed."),
    413: ("payload_too_large", "Request body too large."),
    415: ("unsupported_media_type", "Unsupported media type."),
    429: ("rate_limited", "Too many requests."),
}


# Installs one handler per error family on the app. Called once from main.py.
def register_error_handlers(app: FastAPI) -> None:
    # Our own errors (ValidationError, NotFoundError, ConflictError...).
    @app.exception_handler(SaathiError)
    async def handle_saathi_error(request: Request, exc: SaathiError) -> JSONResponse:
        status = _status_for(exc)
        if isinstance(exc, TenantIsolationError):
            log.warning("security.tenant_isolation_violation", path=request.url.path)
        message = exc.message if status < 500 else "An internal error occurred."
        return JSONResponse(status_code=status, content=_body(request, exc.code, message))

    # Framework errors like 404 'no such URL' or 405 'wrong method'.
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(exc.status_code, ("http_error", "Request failed."))
        if exc.status_code >= 500:
            code, message = "internal_error", "An internal error occurred."
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(request, code, message),
            headers=exc.headers,  # keeps e.g. "Allow" on 405
        )

    # The request body didn't match the expected shape (422).
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

    # Anything unexpected: log the full details for us, answer a generic 500 to the client.
    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500, content=_body(request, "internal_error", "An internal error occurred.")
        )
