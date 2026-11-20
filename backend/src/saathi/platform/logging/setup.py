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

# logging — Python's built-in logging.
import logging

# sys — Python runtime details (output streams, exit codes).
import sys

# structlog — structured logging (JSON log lines).
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
    # Turn the level name (e.g. 'INFO') into Python's number for it; unknown names -> INFO.
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    # Steps applied to every log line: add request context, level and timestamp.
    shared: list[structlog.types.Processor] = [
        # add request_id/tenant_id that were bound for this request,
        structlog.contextvars.merge_contextvars,
        # add the level (info, warning...),
        structlog.processors.add_log_level,
        # add an ISO timestamp in UTC.
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    # The final step that turns a log entry into text:
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )

    # Settings for logs written by our own code.
    structlog.configure(
        # The steps, in order:
        processors=[
            # the shared steps (request context, level, timestamp),
            *shared,
            # add stack information when asked for,
            structlog.processors.StackInfoRenderer(),
            # turn an exception into readable text,
            structlog.processors.format_exc_info,
            # then write it as JSON (or coloured text).
            renderer,
        ],
        # Drop log lines below the chosen level.
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        # Write to standard output (Docker collects it from there).
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        # Build each logger once and reuse it (faster).
        cache_logger_on_first_use=True,
    )

    # Settings for logs written by other libraries, so they look the same.
    handler = logging.StreamHandler(sys.stdout)
    # Give the handler a formatter that:
    handler.setFormatter(
        # Formats library log lines with structlog:
        structlog.stdlib.ProcessorFormatter(
            # first adds the shared fields and the logger's name,
            foreign_pre_chain=[*shared, structlog.stdlib.add_logger_name],
            # then runs these steps:
            processors=[
                # remove structlog's internal bookkeeping fields,
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                # turn an exception into readable text,
                structlog.processors.format_exc_info,
                # and write it in the same format as our own logs.
                renderer,
            ],
        )
    )
    # The root logger: every library's logger passes its lines up to it.
    root = logging.getLogger()
    # Replace its handlers with ours, so everything goes through one place.
    root.handlers = [handler]
    # Apply the chosen level.
    root.setLevel(log_level)

    # For each library that installs its own handler...
    for name in _REROUTED:
        # ...get its logger,
        lg = logging.getLogger(name)
        # remove its own handlers,
        lg.handlers = []
        # and pass its lines up to the root (our format).
        lg.propagate = True
    # For each logger we don't want at all...
    for name in _SILENCED:
        # ...switch it off.
        logging.getLogger(name).disabled = True
    # For each chatty library...
    for name in _WARNING_ONLY:
        # ...show only warnings and errors.
        logging.getLogger(name).setLevel(max(log_level, logging.WARNING))
