# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Helpers that give tests a REAL Postgres database, logged in as the app role so row-level
#       security applies.
# How to run: Used automatically by the tests; nothing to run directly.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Fixtures for tests that need a REAL Postgres (R37): RLS, SQL repositories, migrations.

Opt in with:
    RUN_DB_TESTS=1
    TEST_DATABASE_URL=postgresql+asyncpg://<owner>@host:port/<db>      (schema owner / superuser)
    TEST_APP_DATABASE_URL=postgresql+asyncpg://saathi_app:...@host:port/<db>   (NOBYPASSRLS)

Use a throwaway database: every test starts by deleting all rows. Never point these at a real
environment. Without the variables, every test using these fixtures is skipped.
"""

# os — talks to the operating system (environment variables, files).
import os

# subprocess — runs another program.
import subprocess

# sys — Python runtime details (output streams, exit codes).
import sys

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From pathlib — file and folder paths: Path = a file or folder path.
from pathlib import Path

# pytest — the test framework.
import pytest

# From sqlalchemy — SQLAlchemy, our database toolkit: text = a raw SQL snippet.
from sqlalchemy import text

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncEngine =
#   the async connection pool; AsyncSession = one unit of database work; async_sessionmaker =
#   factory that creates sessions; create_async_engine = builds a connection pool.
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# From sqlalchemy.pool — connection-pool options: NullPool = no pooling (connect, use, close).
from sqlalchemy.pool import NullPool

BACKEND = Path(__file__).resolve().parents[1]
OWNER_URL = os.environ.get("TEST_DATABASE_URL", "")
APP_URL = os.environ.get("TEST_APP_DATABASE_URL", "")
REQUESTED = os.environ.get("RUN_DB_TESTS") == "1"
if REQUESTED and not (OWNER_URL and APP_URL):
    # Fail loudly: silently skipping the isolation tests in CI would be a false green.
    raise RuntimeError("RUN_DB_TESTS=1 needs TEST_DATABASE_URL and TEST_APP_DATABASE_URL")
ENABLED = REQUESTED

requires_db = pytest.mark.skipif(
    not ENABLED, reason="set RUN_DB_TESTS=1, TEST_DATABASE_URL and TEST_APP_DATABASE_URL"
)


def _alembic(*args: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-only
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env={**os.environ, "MIGRATION_DATABASE_URL": OWNER_URL},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout + result.stderr


@pytest.fixture(scope="session")
def migrated_db() -> str:
    """Prove every migration's downgrade works (R25), then leave the schema at head."""
    if not ENABLED:
        pytest.skip("real Postgres not configured")
    _alembic("upgrade", "head")
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
    return _alembic("current")


def _engine(url: str) -> AsyncEngine:
    return create_async_engine(url, poolclass=NullPool)


@pytest.fixture
async def owner_engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    engine = _engine(OWNER_URL)
    async with engine.begin() as conn:  # every test starts empty
        await conn.execute(text("TRUNCATE tenants CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def app_sessionmaker(
    owner_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions as saathi_app: RLS applies exactly as in production."""
    engine = _engine(APP_URL)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
