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
        url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


# A factory that creates a new 'session' (a unit of database work) when asked.
def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


# One tiny query to prove the database answers (used by /ready).
async def ping_database(engine: AsyncEngine) -> None:
    """Readiness probe: one round trip. Raises if the database is unreachable."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
