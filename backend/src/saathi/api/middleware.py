# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Code that wraps EVERY request: gives it an id, adds that id to all its log lines and to
#       the response, and writes one summary log line.
# Why: With an id you can follow one request through all the logs. The summary line (method,
#      path, status, time) is how we see traffic.
# Security: 🔒 A caller-supplied id is only accepted if it looks safe, and query strings are
#           never logged (they can contain tokens or personal data).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Request-context middleware (pure ASGI - safe for SSE streaming, unlike BaseHTTPMiddleware).

Binds a request id to every log line and emits one "http.request" access event per request
(method, path, status, duration). Query strings are never logged: they can carry tokens or PII.
"""

# re — regular expressions (text patterns).
import re

# time — clocks and timers.
import time

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# structlog — structured logging (JSON log lines).
import structlog

# From starlette.types — low-level ASGI web-server types: ASGIApp = an ASGI web app; Message =
#   one ASGI event; Receive = reads ASGI events; Scope = details of the current request; Send =
#   writes ASGI events.
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# What a safe request id looks like: 8-64 letters, digits or dashes.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
_PROBES = frozenset({"/health", "/ready"})  # polled every few seconds: debug level only


# The wrapper itself. Written as 'pure ASGI' so it also works for streaming responses later
# (Phase 3).
class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    # Runs for every request. `scope` describes the request; `send` delivers the response.
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Not an HTTP request (e.g. a start-up event)? Pass it straight through.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Read the incoming headers to look for a caller's request id.
        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")
        # Accept a caller's id only if well-formed (prevents log injection).
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid4().hex

        # Start each request with clean log context, then attach the request id to every log
        # line it produces.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        # Also store the id on the request, so error responses can include it (api/errors.py).
        scope.setdefault("state", {})["request_id"] = request_id

        status = 500  # if the app raises before responding, the server returns 500
        # Start a stopwatch to measure how long the request takes.
        started = time.perf_counter()

        # Wraps `send`: when the response starts, remember its status and add the x-request-id
        # header.
        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        # Run the actual request. `finally` makes sure the summary line is written even if it
        # crashed.
        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope.get("path", "")
            log = structlog.get_logger()  # fresh proxy: follows the current configuration
            # Health checks run every few seconds - log them quietly (debug) so they don't flood
            # the logs.
            emit = log.debug if path in _PROBES else log.info
            emit(
                "http.request",
                method=scope.get("method"),
                path=path,
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
