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

# The backend folder (where alembic.ini lives).
BACKEND = Path(__file__).resolve().parents[1]
# Address of the throwaway test database as its OWNER (can create tables).
OWNER_URL = os.environ.get("TEST_DATABASE_URL", "")
# Address of the same database as saathi_app (row-level security applies).
APP_URL = os.environ.get("TEST_APP_DATABASE_URL", "")
# Did the caller ask for real-database tests (RUN_DB_TESTS=1)?
REQUESTED = os.environ.get("RUN_DB_TESTS") == "1"
# Asked for them but the addresses are missing:
if REQUESTED and not (OWNER_URL and APP_URL):
    # Fail loudly: silently skipping the isolation tests in CI would be a false green.
    raise RuntimeError("RUN_DB_TESTS=1 needs TEST_DATABASE_URL and TEST_APP_DATABASE_URL")
# Real-database tests run only when asked for.
ENABLED = REQUESTED

# A marker: tests decorated with @requires_db are skipped unless enabled.
requires_db = pytest.mark.skipif(
    not ENABLED, reason="set RUN_DB_TESTS=1, TEST_DATABASE_URL and TEST_APP_DATABASE_URL"
)


# Run an Alembic command against the test database and return its output.
def _alembic(*args: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-only
        # python -m alembic <args>,
        [sys.executable, "-m", "alembic", *args],
        # from the backend folder,
        cwd=BACKEND,
        # with the owner address as MIGRATION_DATABASE_URL,
        env={**os.environ, "MIGRATION_DATABASE_URL": OWNER_URL},
        # capturing the output,
        capture_output=True,
        # as text,
        text=True,
        # and failing the test if Alembic fails.
        check=True,
    )
    # Everything Alembic printed.
    return result.stdout + result.stderr


# A fixture that runs once per test session:
@pytest.fixture(scope="session")
# it prepares the database schema.
def migrated_db() -> str:
    """Prove every migration's downgrade works (R25), then leave the schema at head."""
    # Not enabled:
    if not ENABLED:
        # skip every test that needs it.
        pytest.skip("real Postgres not configured")
    # Apply all migrations,
    _alembic("upgrade", "head")
    # undo them all (proves every downgrade works),
    _alembic("downgrade", "base")
    # and apply them again.
    _alembic("upgrade", "head")
    # Return the current migration id.
    return _alembic("current")


# A database connection pool without pooling (each use opens a fresh connection).
def _engine(url: str) -> AsyncEngine:
    # Create it.
    return create_async_engine(url, poolclass=NullPool)


# A fixture created fresh for each test:
@pytest.fixture
# it needs the migrated database first.
async def owner_engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    # Connect as the owner.
    engine = _engine(OWNER_URL)
    async with engine.begin() as conn:  # every test starts empty
        await conn.execute(text("TRUNCATE tenants CASCADE"))
    # Lend the engine to the test.
    yield engine
    # Close it afterwards.
    await engine.dispose()


# A fixture created fresh for each test:
@pytest.fixture
# sessions that connect as saathi_app, the role the real app uses...
async def app_sessionmaker(
    # ...after owner_engine has emptied the tables.
    owner_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions as saathi_app: RLS applies exactly as in production."""
    # Connect as saathi_app.
    engine = _engine(APP_URL)
    # Lend a session factory to the test.
    yield async_sessionmaker(engine, expire_on_commit=False)
    # Close it afterwards.
    await engine.dispose()
