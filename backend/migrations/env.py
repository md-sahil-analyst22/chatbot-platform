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
    # analytics (usage_logs),
    "analytics",
    # conversation (contacts, conversations, messages),
    "conversation",
    # credentials (provider_credentials),
    "credentials",
    # handoff (handoffs),
    "handoff",
    # knowledge (sources, chunks, faqs),
    "knowledge",
    # leads (leads),
    "leads",
    # tenancy (tenants, user_accounts, bots, bot_config_versions, assets, audit_logs).
    "tenancy",
)
# Import each module's table classes...
for _module in MODULES_WITH_TABLES:
    # ...so they register themselves on Base.metadata (Alembic compares against it).
    importlib.import_module(f"saathi.modules.{_module}.adapters.orm")

# Alembic's settings from alembic.ini.
config = context.config
# If alembic.ini was found...
if config.config_file_name is not None:
    # ...use its logging settings.
    fileConfig(config.config_file_name)

# The full description of every table, for Alembic to compare with the database.
target_metadata = Base.metadata


# Read the migration database address; stop if it's missing.
def _url() -> str:
    # Read the address from the environment.
    url = os.environ.get("MIGRATION_DATABASE_URL")
    # Missing...
    if not url:
        # ...stop with a clear message.
        raise RuntimeError("MIGRATION_DATABASE_URL is not set")
    # Return it.
    return url


# Write the SQL out instead of running it (used by `make schema-sql`).
def run_migrations_offline() -> None:
    # Set Alembic up with just the address (no connection) and values written into the SQL.
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    # Start a (pretend) transaction...
    with context.begin_transaction():
        # ...and write out the migrations' SQL.
        context.run_migrations()


# Run the migrations on an open connection, in one transaction.
def _run(connection: Connection) -> None:
    # Set Alembic up with the live connection; also compare column types.
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    # Start a real transaction...
    with context.begin_transaction():
        # ...and apply the migrations inside it (all or nothing).
        context.run_migrations()


# Normal mode: connect and apply the migrations.
async def run_migrations_online() -> None:
    # Create a connection pool from the address...
    engine = async_engine_from_config(
        {"sqlalchemy.url": _url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    # Open one connection...
    async with engine.connect() as connection:
        # ...and run the migrations on it (Alembic itself is not async, so run_sync bridges
        #   it).
        await connection.run_sync(_run)
    # Close the connection pool.
    await engine.dispose()


# `alembic upgrade --sql` asks for offline mode...
if context.is_offline_mode():
    # ...so write SQL instead of running it.
    run_migrations_offline()
# Otherwise (the normal case)...
else:
    # ...connect and apply the migrations.
    asyncio.run(run_migrations_online())
