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

# This migration's id.
revision: str = "0001"
# The migration before it: none (this is the first).
down_revision: str | None = None
# Not used (no parallel migration branches).
branch_labels: str | Sequence[str] | None = None
# Not used (no extra dependencies).
depends_on: str | Sequence[str] | None = None


# Apply this migration:
def upgrade() -> None:
    # switch on pgvector (does nothing if it's already on).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


# Undo this migration:
def downgrade() -> None:
    # switch pgvector off again.
    op.execute("DROP EXTENSION IF EXISTS vector")
