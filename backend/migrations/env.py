# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Alembic's start-up file: connects to the database and runs the migrations.
# Security: 🔒 Uses MIGRATION_DATABASE_URL (the table-owner role), never the app's own login
#           (R24).
# Run: In production this runs automatically before the API starts (the `migrate` service).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Alembic environment (async). URL from MIGRATION_DATABASE_URL (schema-owner role)."""

import asyncio
import importlib
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

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
