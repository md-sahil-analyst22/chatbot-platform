# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Migration 1: switches on the `vector` extension (pgvector), needed to store and search
#       embeddings.
# Plain words: A migration = a numbered, reversible change to the database structure. upgrade()
#              applies it, downgrade() undoes it.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Baseline: enable pgvector. Tables + RLS policies arrive in the Phase 1 migration (P1.5/P1.6).

Revision ID: 0001
Revises:
Create Date: 2026-11-11
"""

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# From alembic — the database migration tool: op = commands that change tables.
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
