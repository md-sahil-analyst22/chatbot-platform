# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Alembic's start-up file: connects to the database and runs the migrations.
# Security: 🔒 Uses MIGRATION_DATABASE_URL (the table-owner role), never the app's own login
#           (R24).
# Run: In production this runs automatically before the API starts (the `migrate` service).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Alembic environment (async). URL from MIGRATION_DATABASE_URL (schema-owner role)."""

# asyncio — runs many waiting tasks at once (async).
import asyncio

# importlib — imports a module by name while the program runs.
import importlib

# os — talks to the operating system (environment variables, files).
import os

# From logging.config — logging set-up helpers: fileConfig = loads logging settings from
#   alembic.ini.
from logging.config import fileConfig

# From alembic — the database migration tool: context = details of the migration being run.
from alembic import context

# From sqlalchemy — SQLAlchemy, our database toolkit: pool = connection-pool options.
from sqlalchemy import pool

# From sqlalchemy.engine — low-level database connection types: Connection = one open database
#   connection.
from sqlalchemy.engine import Connection

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools:
#   async_engine_from_config = builds a connection pool from settings.
from sqlalchemy.ext.asyncio import async_engine_from_config

# From saathi.platform.db.base — shared building blocks for table classes: Base = parent of
#   every table class.
from saathi.platform.db.base import Base

# Register every module's tables on Base.metadata (add a module here when it gets tables).
MODULES_WITH_TABLES = (
    "analytics",
    "conversation",
    "credentials",
    "handoff",
    "knowledge",
    "leads",
    "tenancy",
)
for _module in MODULES_WITH_TABLES:
    importlib.import_module(f"saathi.modules.{_module}.adapters.orm")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# Read the migration database address; stop if it's missing.
def _url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise RuntimeError("MIGRATION_DATABASE_URL is not set")
    return url


# Write the SQL out instead of running it (used by `make schema-sql`).
def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


# Run the migrations on an open connection, in one transaction.
def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


# Normal mode: connect and apply the migrations.
async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        {"sqlalchemy.url": _url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
