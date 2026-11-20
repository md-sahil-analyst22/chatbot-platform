# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Logs from libraries come out in the same structured format as ours.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Standard-library logs (uvicorn, SQLAlchemy, ...) come out as the same structured JSON."""

# json — reads and writes JSON text.
import json

# logging — Python's built-in logging.
import logging

# From collections.abc — standard type names for collections: Iterator = type for a one-pass
#   loop source.
from collections.abc import Iterator

# pytest — the test framework.
import pytest

# structlog — structured logging (JSON log lines).
import structlog

# From saathi.platform.logging.setup — logging set-up: configure_logging = sets up logging.
from saathi.platform.logging.setup import configure_logging


# A fixture that runs automatically around every test in this file:
@pytest.fixture(autouse=True)
# it saves the logging set-up and restores it afterwards.
def restore_logging() -> Iterator[None]:
    # The root logger.
    root = logging.getLogger()
    # Save its handlers and level.
    handlers, level = root.handlers[:], root.level
    # The uvicorn access logger (our set-up switches it off).
    access = logging.getLogger("uvicorn.access")
    # Run the test.
    yield
    # Afterwards: put the handlers and level back,
    root.handlers, root.level = handlers, level
    # switch the access logger back on,
    access.disabled = False
    # reset structlog,
    structlog.reset_defaults()
    # and forget any bound request context.
    structlog.contextvars.clear_contextvars()


# Library log lines come out as JSON that includes the request id.
def test_stdlib_records_are_rendered_as_json_with_request_id(
    # capsys captures what's printed.
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Set up logging in JSON mode.
    configure_logging("INFO", json_logs=True)
    # Pretend we're inside request 'req-1'.
    structlog.contextvars.bind_contextvars(request_id="req-1")
    # A library (uvicorn) writes a warning.
    logging.getLogger("uvicorn.error").warning("server started")
    # Read the last printed line as JSON.
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    # It has the message,
    assert line["event"] == "server started"
    # the level,
    assert line["level"] == "warning"
    # the request id,
    assert line["request_id"] == "req-1"
    # which logger wrote it,
    assert line["logger"] == "uvicorn.error"
    # and a timestamp.
    assert "timestamp" in line


# uvicorn's access log is off and httpx only shows warnings.
def test_uvicorn_access_log_is_replaced_and_httpx_is_quiet() -> None:
    # Set up logging, even at the most detailed level.
    configure_logging("DEBUG", json_logs=True)
    # The access log is switched off.
    assert logging.getLogger("uvicorn.access").disabled
    # httpx stays at warning level (its info lines can contain keys in URLs).
    assert logging.getLogger("httpx").level == logging.WARNING
