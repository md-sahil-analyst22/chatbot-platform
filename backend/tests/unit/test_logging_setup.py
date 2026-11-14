"""Standard-library logs (uvicorn, SQLAlchemy, ...) come out as the same structured JSON."""

import json
import logging
from collections.abc import Iterator

import pytest
import structlog

from saathi.platform.logging.setup import configure_logging


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    access = logging.getLogger("uvicorn.access")
    yield
    root.handlers, root.level = handlers, level
    access.disabled = False
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


def test_stdlib_records_are_rendered_as_json_with_request_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO", json_logs=True)
    structlog.contextvars.bind_contextvars(request_id="req-1")
    logging.getLogger("uvicorn.error").warning("server started")
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["event"] == "server started"
    assert line["level"] == "warning"
    assert line["request_id"] == "req-1"
    assert line["logger"] == "uvicorn.error"
    assert "timestamp" in line


def test_uvicorn_access_log_is_replaced_and_httpx_is_quiet() -> None:
    configure_logging("DEBUG", json_logs=True)
    assert logging.getLogger("uvicorn.access").disabled
    assert logging.getLogger("httpx").level == logging.WARNING
