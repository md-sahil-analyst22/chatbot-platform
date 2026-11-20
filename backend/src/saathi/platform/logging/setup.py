# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Configures logging for the whole app, once at start-up.
# Result: Every log line has the same structure (JSON in production) and carries
#         request_id/tenant_id automatically - including logs from uvicorn and libraries.
# Security: 🔒 Noisy libraries that log full URLs (httpx) are limited to warnings, because URLs
#           can contain keys.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Structured logging (structlog). request_id / tenant_id are bound per request via contextvars.

Everything goes to stdout in one format: JSON outside local development, coloured console
locally. Standard-library loggers (uvicorn, SQLAlchemy, httpx, arq) are routed through the same
processors, so the platform's log collector sees one consistent shape (R18).
"""

import logging
import sys

import structlog

# Uvicorn's access log is replaced by RequestContextMiddleware's "http.request" event, which
# carries request_id/tenant_id and never logs query strings (they can contain tokens or PII).
# Uvicorn's own access log is turned off; our middleware writes a safer one.
_SILENCED = ("uvicorn.access",)
# Loggers that install their own handlers; make them propagate to the root handler instead.
_REROUTED = ("uvicorn", "uvicorn.error", "arq")
# Chatty at INFO (httpx logs every request URL, which can include keys in query strings).
_WARNING_ONLY = ("httpx", "httpcore")


# Called by main.py. `json_logs=False` gives coloured, readable logs on a laptop.
def configure_logging(level: str = "INFO", *, json_logs: bool = True) -> None:
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    # Steps applied to every log line: add request context, level and timestamp.
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )

    # Settings for logs written by our own code.
    structlog.configure(
        processors=[
            *shared,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Settings for logs written by other libraries, so they look the same.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[*shared, structlog.stdlib.add_logger_name],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    for name in _REROUTED:
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    for name in _SILENCED:
        logging.getLogger(name).disabled = True
    for name in _WARNING_ONLY:
        logging.getLogger(name).setLevel(max(log_level, logging.WARNING))
