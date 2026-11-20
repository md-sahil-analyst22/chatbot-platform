# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Migration 3: adds resolve_user_membership(), which tells the login checker which
#       workspace and role a user has.
# Safe: Only adds things, so it works while the old app version is still running.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Login -> tenant membership lookup (P1.7, ADR-0007).

Adds resolve_user_membership(), a narrow SECURITY DEFINER function the app role calls before a
tenant context exists, and the index that serves it. Additive only: safe during a rolling deploy.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-15
"""

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# From alembic — the database migration tool: op = commands that change tables.
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Add the lookup index and the narrow lookup function.
def upgrade() -> None:
    # serves: login -> membership lookup on every authenticated request
    op.create_index("ix_user_accounts_auth_user_id", "user_accounts", ["auth_user_id"])
    # Returns ids and roles only - nothing that could leak tenant data. search_path is pinned.
    op.execute(
        """
        CREATE FUNCTION resolve_user_membership(p_auth_user_id text)
        RETURNS TABLE (tenant_id uuid, role text)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT u.tenant_id, u.role::text
            FROM public.user_accounts u
            WHERE u.auth_user_id = p_auth_user_id
            ORDER BY u.created_at
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION resolve_user_membership(text) FROM PUBLIC")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'saathi_app') THEN
                GRANT EXECUTE ON FUNCTION resolve_user_membership(text) TO saathi_app;
            END IF;
            -- Supabase Data API roles must not be able to enumerate memberships.
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON FUNCTION resolve_user_membership(text) FROM anon, authenticated;
            END IF;
        END
        $$
        """
    )


# Remove them again.
def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS resolve_user_membership(text)")
    op.drop_index("ix_user_accounts_auth_user_id", table_name="user_accounts")
