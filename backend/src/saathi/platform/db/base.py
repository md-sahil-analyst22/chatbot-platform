"""Declarative base shared by all module ORM adapters (one metadata for Alembic).

The schema itself is created only by Alembic migrations (R25); these classes describe it for the
ORM and must stay in sync with the latest migration.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Every timestamp is timezone-aware (timestamptz); naive datetimes are a bug magnet.
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


def uuid_pk() -> Mapped[uuid.UUID]:
    """Primary key; the app normally supplies uuid4, the default helps manual inserts."""
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def tenant_fk() -> Mapped[uuid.UUID]:
    """tenant_id NOT NULL -> tenants(id) (R23). Deleting a tenant deletes all its data."""
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )


def created_at() -> Mapped[datetime]:
    return mapped_column(server_default=func.now(), nullable=False)


def updated_at() -> Mapped[datetime]:
    return mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
