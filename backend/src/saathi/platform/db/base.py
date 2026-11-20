# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Shared building blocks for every database table class (the 'ORM' models).
# Why: One parent class and reusable column recipes keep all 16 tables consistent: same id
#      style, timezone-aware times, tenant link.
# Note: Tables are CREATED by migrations (backend/migrations), not by this code. These classes
#       describe them for Python.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Declarative base shared by all module ORM adapters (one metadata for Alembic).

The schema itself is created only by Alembic migrations (R25); these classes describe it for the
ORM and must stay in sync with the latest migration.
"""

# uuid — unique ids (UUIDs).
import uuid

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From sqlalchemy — SQLAlchemy, our database toolkit: DateTime = date+time column type;
#   ForeignKey = link to a row in another table; MetaData = the collection of table definitions;
#   func = SQL functions such as now() or max(); text = a raw SQL snippet.
from sqlalchemy import DateTime, ForeignKey, MetaData, func, text

# From sqlalchemy.dialects.postgresql — Postgres-only column types: UUID = UUID column type.
from sqlalchemy.dialects.postgresql import UUID

# From sqlalchemy.orm — SQLAlchemy's table-class tools: DeclarativeBase = parent class for table
#   classes; Mapped = type hint for a column; mapped_column = defines one column.
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable names for indexes and constraints, so migrations stay readable.
NAMING_CONVENTION = {
    # Index names: ix_<column>.
    "ix": "ix_%(column_0_label)s",
    # Unique-rule names: uq_<table>_<column>.
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # Check-rule names: ck_<table>_<rule>.
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    # Foreign-key names: fk_<table>_<column>_<other table>.
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    # Primary-key names: pk_<table>.
    "pk": "pk_%(table_name)s",
}


# Parent class of every table. type_annotation_map makes every datetime timezone-aware.
class Base(DeclarativeBase):
    # Every table uses the naming rules above.
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Every timestamp is timezone-aware (timestamptz); naive datetimes are a bug magnet.
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


# Recipe for an `id` column: a random UUID.
def uuid_pk() -> Mapped[uuid.UUID]:
    """Primary key; the app normally supplies uuid4, the default helps manual inserts."""
    # A UUID column that is the primary key; the database fills it with a random id.
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


# 🔒 Recipe for `tenant_id`: required, and deleting a tenant deletes all its data.
def tenant_fk() -> Mapped[uuid.UUID]:
    """tenant_id NOT NULL -> tenants(id) (R23). Deleting a tenant deletes all its data."""
    # A required UUID column linked to tenants.id; deleting the tenant deletes this row.
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )


# Recipe for 'when was this row created' (set by the database).
def created_at() -> Mapped[datetime]:
    # Filled by the database with the current time when a row is inserted; never empty.
    return mapped_column(server_default=func.now(), nullable=False)


# Recipe for 'when was this row last changed'.
def updated_at() -> Mapped[datetime]:
    # Set to now() on insert, and updated to now() whenever the row changes.
    return mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
