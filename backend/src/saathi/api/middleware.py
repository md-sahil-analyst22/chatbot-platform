"""Request-context middleware (pure ASGI - safe for SSE streaming, unlike BaseHTTPMiddleware).

Binds a request id to every log line and emits one "http.request" access event per request
(method, path, status, duration). Query strings are never logged: they can carry tokens or PII.
"""

import re
import time
from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
_PROBES = frozenset({"/health", "/ready"})  # polled every few seconds: debug level only


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")
        # Accept a caller's id only if well-formed (prevents log injection).
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid4().hex

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        status = 500  # if the app raises before responding, the server returns 500
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope.get("path", "")
            log = structlog.get_logger()  # fresh proxy: follows the current configuration
            emit = log.debug if path in _PROBES else log.info
            emit(
                "http.request",
                method=scope.get("method"),
                path=path,
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
