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

# structlog — structured logging (JSON log lines).
import structlog

# From fastapi — the web framework that turns Python functions into web endpoints: FastAPI = the
#   web app object; Request = the incoming HTTP request.
from fastapi import FastAPI, Request

# From fastapi.exceptions — FastAPI's errors: RequestValidationError = raised when request data
#   is invalid (422).
from fastapi.exceptions import RequestValidationError

# From fastapi.responses — ready-made HTTP responses: JSONResponse = an HTTP response with a
#   JSON body.
from fastapi.responses import JSONResponse

# From starlette.exceptions — Starlette (the base FastAPI is built on) errors: HTTPException =
#   framework errors such as 404 or 405.
from starlette.exceptions import HTTPException as StarletteHTTPException

# From saathi.platform.errors — our error types: AuthenticationError = 401 not logged in;
#   AuthorizationError = 403 role not allowed; ConflictError = 409 clash with existing data;
#   NotFoundError = 404 not found; ProviderError = a vendor failed; ProviderTimeoutError = a
#   vendor was too slow; RateLimitError = 429 too many requests; SaathiError = parent of all our
#   errors; TenantIsolationError = tried to cross tenants; ValidationError = 422 invalid input.
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

# The logger for this file.
log = structlog.get_logger()

# Which of our error types becomes which HTTP status code. Order matters: the first match wins.
_STATUS: list[tuple[type[SaathiError], int]] = [
    # Invalid input -> 422.
    (ValidationError, 422),
    # Not found -> 404.
    (NotFoundError, 404),
    # Conflict with existing data -> 409.
    (ConflictError, 409),
    # Not logged in -> 401.
    (AuthenticationError, 401),
    # 🔒 Another tenant's data answers 404 'not found', so nobody can even learn it exists.
    (TenantIsolationError, 404),  # don't reveal that another tenant's object exists
    # Logged in but role too low -> 403.
    (AuthorizationError, 403),
    # Too many requests -> 429.
    (RateLimitError, 429),
    # Vendor too slow -> 504.
    (ProviderTimeoutError, 504),
    # Vendor failed -> 502.
    (ProviderError, 502),
]


# Look up the HTTP status for an error; anything unknown is a 500.
def _status_for(exc: SaathiError) -> int:
    # Check each (error type, status) pair in order...
    for typ, status in _STATUS:
        # ...and if the error is of that type (or a child of it)...
        if isinstance(exc, typ):
            # ...use that status.
            return status
    # Anything not in the list is an unexpected server error -> 500.
    return 500


# Build the standard error JSON, including the request id so a user can quote it when reporting
# a problem.
def _body(
    request: Request, code: str, message: str, details: list[dict[str, object]] | None = None
) -> dict[str, object]:
    # Build the 'error' part of the JSON body:
    error: dict[str, object] = {
        # a short machine-readable code, e.g. 'not_found',
        "code": code,
        # a human-readable message,
        "message": message,
        # and the request id, so support can find this request in the logs.
        "request_id": getattr(request.state, "request_id", None),
    }
    # Extra details (which fields were invalid) only when there are some.
    if details:
        # Add them to the body.
        error["details"] = details
    # The final shape: {"error": {...}}.
    return {"error": error}


# Framework-raised HTTP errors (unknown route, wrong method, ...) mapped to our codes, with fixed
# messages so nothing raised by a library is echoed back to the client.
# Fixed codes and messages for errors raised by the web framework itself (unknown URL, wrong
# method...).
_HTTP_CODES: dict[int, tuple[str, str]] = {
    # 400 -> bad_request.
    400: ("bad_request", "Bad request."),
    # 401 -> unauthenticated.
    401: ("unauthenticated", "Authentication required."),
    # 403 -> forbidden.
    403: ("forbidden", "Forbidden."),
    # 404 -> not_found (e.g. a URL that doesn't exist).
    404: ("not_found", "Not found."),
    # 405 -> method_not_allowed (e.g. DELETE on a GET-only URL).
    405: ("method_not_allowed", "Method not allowed."),
    # 413 -> payload_too_large.
    413: ("payload_too_large", "Request body too large."),
    # 415 -> unsupported_media_type.
    415: ("unsupported_media_type", "Unsupported media type."),
    # 429 -> rate_limited.
    429: ("rate_limited", "Too many requests."),
}


# Installs one handler per error family on the app. Called once from main.py.
def register_error_handlers(app: FastAPI) -> None:
    # Our own errors (ValidationError, NotFoundError, ConflictError...).
    @app.exception_handler(SaathiError)
    # Handles every error from our own SaathiError family.
    async def handle_saathi_error(request: Request, exc: SaathiError) -> JSONResponse:
        # Pick the HTTP status for this error type.
        status = _status_for(exc)
        # 🔒 Someone tried to reach another tenant's data...
        if isinstance(exc, TenantIsolationError):
            # ...so log a security warning (the caller just sees 404).
            log.warning("security.tenant_isolation_violation", path=request.url.path)
        # 🔒 Show our message for 4xx errors; hide details of server errors (5xx).
        message = exc.message if status < 500 else "An internal error occurred."
        # Send the JSON error answer.
        return JSONResponse(status_code=status, content=_body(request, exc.code, message))

    # Framework errors like 404 'no such URL' or 405 'wrong method'.
    @app.exception_handler(StarletteHTTPException)
    # Handles framework errors (unknown URL, wrong method...).
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Look up our code and message for this status, or use a generic one.
        code, message = _HTTP_CODES.get(exc.status_code, ("http_error", "Request failed."))
        # Server errors (5xx)...
        if exc.status_code >= 500:
            # ...get a generic message that reveals nothing.
            code, message = "internal_error", "An internal error occurred."
        # Send the JSON error answer:
        return JSONResponse(
            # with the original status code,
            status_code=exc.status_code,
            # our standard body,
            content=_body(request, code, message),
            headers=exc.headers,  # keeps e.g. "Allow" on 405
        )

    # The request body didn't match the expected shape (422).
    @app.exception_handler(RequestValidationError)
    # Handles invalid request data (wrong types, missing fields, unknown fields).
    async def handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Field locations and error types only - never echo submitted values (may contain PII).
        details: list[dict[str, object]] = [
            {"loc": list(e.get("loc", ())), "type": e.get("type")} for e in exc.errors()
        ]
        # Send 422 with the list of problems:
        return JSONResponse(
            # status 422,
            status_code=422,
            # standard body plus the details.
            content=_body(request, "validation_error", "Request validation failed.", details),
        )

    # Anything unexpected: log the full details for us, answer a generic 500 to the client.
    @app.exception_handler(Exception)
    # Last safety net: any error nobody expected.
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log it with the full stack trace (in OUR logs only, never in the answer).
        log.exception("unhandled_error", path=request.url.path)
        # 🔒 The caller only gets a generic 500 message.
        return JSONResponse(
            status_code=500, content=_body(request, "internal_error", "An internal error occurred.")
        )
