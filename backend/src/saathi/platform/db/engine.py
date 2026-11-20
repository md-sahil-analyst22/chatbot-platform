# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Creates the database connection pool and the factory that makes database sessions.
# Used by: bootstrap/container.py, once at start-up.
# Plain words: A 'pool' keeps a few connections open and lends them out, which is much faster
#              than connecting for every request.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Async engine + session factory. One engine per process."""

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


# Create the pool: up to 10 connections (+5 extra under load), checked before use, renewed every
# 30 minutes.
def build_engine(url: str) -> AsyncEngine:
    # Pool sized for a small instance; revisit with load-test numbers (P6.4) and the
    # managed-Postgres connection limit (use the provider's pooler in production).
    return create_async_engine(
        # the database address (with user and password),
        url,
        # keep up to 10 connections open,
        pool_size=10,
        # allow 5 extra temporary ones under heavy load,
        max_overflow=5,
        # test a connection before using it (drops dead ones),
        pool_pre_ping=True,
        # replace connections older than 30 minutes (1800 s).
        pool_recycle=1800,
    )


# A factory that creates a new 'session' (a unit of database work) when asked.
def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after a commit.
    return async_sessionmaker(engine, expire_on_commit=False)


# One tiny query to prove the database answers (used by /ready).
async def ping_database(engine: AsyncEngine) -> None:
    """Readiness probe: one round trip. Raises if the database is unreachable."""
    # Borrow a connection from the pool...
    async with engine.connect() as conn:
        # ...and run the smallest possible query. An error means the database isn't answering.
        await conn.execute(text("SELECT 1"))
