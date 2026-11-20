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

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable names for indexes and constraints, so migrations stay readable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# Parent class of every table. type_annotation_map makes every datetime timezone-aware.
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Every timestamp is timezone-aware (timestamptz); naive datetimes are a bug magnet.
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


# Recipe for an `id` column: a random UUID.
def uuid_pk() -> Mapped[uuid.UUID]:
    """Primary key; the app normally supplies uuid4, the default helps manual inserts."""
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


# 🔒 Recipe for `tenant_id`: required, and deleting a tenant deletes all its data.
def tenant_fk() -> Mapped[uuid.UUID]:
    """tenant_id NOT NULL -> tenants(id) (R23). Deleting a tenant deletes all its data."""
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )


# Recipe for 'when was this row created' (set by the database).
def created_at() -> Mapped[datetime]:
    return mapped_column(server_default=func.now(), nullable=False)


# Recipe for 'when was this row last changed'.
def updated_at() -> Mapped[datetime]:
    return mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
