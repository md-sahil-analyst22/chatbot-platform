# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Database changes for Phase 2 (knowledge base + answers):
#   1. sources.options      website crawl settings (depth, page budget, include/exclude);
#   2. faqs.embedding       the FAQ question's vector, for 'same meaning' FAQ matching (P2.12);
#   3. unanswered_questions questions the bot said "I'm not sure" to (P2.14), with the same
#                           tenant protections as every other tenant table (R23): tenant_id NOT
#                           NULL, composite foreign keys, forced row-level security.
# Safety: additive only (new nullable columns + a new table), so the app version that is already
#   running keeps working while this runs (R25: expand first). downgrade() removes exactly these.
# P2.9 indexes: HNSW on chunks.embedding, GIN on chunks.tsv and (tenant_id, bot_id) indexes were
#   created in 0002 and are reused; FAQs need no vector index (a bot has tens of FAQs).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Phase 2: crawl options, FAQ embeddings, unanswered questions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22
"""

# From collections.abc — standard type names for collections: Sequence = read-only list type.
from collections.abc import Sequence

# sqlalchemy — column types and SQL helpers for the migration.
import sqlalchemy as sa

# From alembic — the migration tool: op = the operations (create table, add column...).
from alembic import op

# From pgvector.sqlalchemy — pgvector column type: Vector = an embedding vector column.
from pgvector.sqlalchemy import Vector

# From sqlalchemy.dialects.postgresql — Postgres-only types: JSONB = binary JSON.
from sqlalchemy.dialects.postgresql import JSONB

# This migration's id.
revision: str = "0004"
# The migration it follows.
down_revision: str | None = "0003"
# Not used (no branches).
branch_labels: str | Sequence[str] | None = None
# Not used.
depends_on: str | Sequence[str] | None = None

# The platform-wide embedding size (R13): must match chunks.embedding.
EMBEDDING_DIMENSIONS = 1536
# The current tenant, as set per transaction by tenant_session() (same expression as 0002).
_CURRENT_TENANT = "nullif(current_setting('app.tenant_id', true), '')::uuid"


# Apply the changes.
def upgrade() -> None:
    # 1. Crawl settings on sources (NULL for uploaded files and for rows from before Phase 2).
    op.add_column("sources", sa.Column("options", JSONB(), nullable=True))
    # 2. FAQ question vectors (NULL for FAQs created before this migration: never matched until
    #    edited, so nothing is matched on a missing vector).
    op.add_column("faqs", sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True))
    # 3. The unanswered-questions table.
    op.create_table(
        # Its name.
        "unanswered_questions",
        # Random UUID primary key.
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # 🔒 The owning tenant (never NULL, R23).
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        # The bot that was asked.
        sa.Column("bot_id", sa.UUID(), nullable=False),
        # The conversation, if any (NULL outside a chat, e.g. evals).
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        # The question (bounded).
        sa.Column("question", sa.String(length=2000), nullable=False),
        # Reply language code.
        sa.Column("language", sa.String(length=10), nullable=False),
        # Why it wasn't answered.
        sa.Column("reason", sa.String(length=30), nullable=False),
        # Best retrieval score, if any.
        sa.Column("top_score", sa.Double(), nullable=True),
        # Published config version used, if known.
        sa.Column("config_version", sa.Integer(), nullable=True),
        # When it was asked.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Only known reasons.
        sa.CheckConstraint(
            "reason IN ('no_results', 'low_confidence', 'unsupported', 'provider_unavailable')",
            name=op.f("ck_unanswered_questions_reason"),
        ),
        # 🔒 The bot must belong to the same tenant; deleting the bot deletes these rows.
        sa.ForeignKeyConstraint(
            ["tenant_id", "bot_id"],
            ["bots.tenant_id", "bots.id"],
            name=op.f("fk_unanswered_questions_tenant_id_bots"),
            ondelete="CASCADE",
        ),
        # 🔒 The conversation (if any) must belong to the same tenant.
        sa.ForeignKeyConstraint(
            ["tenant_id", "conversation_id"],
            ["conversations.tenant_id", "conversations.id"],
            name=op.f("fk_unanswered_questions_tenant_id_conversations"),
            ondelete="CASCADE",
        ),
        # 🔒 The tenant must exist; deleting the tenant deletes these rows.
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_unanswered_questions_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        # Primary key.
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unanswered_questions")),
    )
    # serves: Studio list of a bot's unanswered questions (newest first) + the bot-delete cascade.
    op.create_index(
        "ix_unanswered_tenant_bot_created",
        "unanswered_questions",
        ["tenant_id", "bot_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    # 🔒 Row-level security, forced even for the table owner, same policy as every tenant table.
    op.execute("ALTER TABLE unanswered_questions ENABLE ROW LEVEL SECURITY")
    # Forced: the owner role is not exempt either.
    op.execute("ALTER TABLE unanswered_questions FORCE ROW LEVEL SECURITY")
    # Rows are visible/writable only for the transaction's tenant (fail closed when unset).
    op.execute(
        "CREATE POLICY tenant_isolation ON unanswered_questions "
        f"USING (tenant_id = {_CURRENT_TENANT}) "
        f"WITH CHECK (tenant_id = {_CURRENT_TENANT})"
    )
    # Privileges: the app role reads/writes rows (RLS applies); Supabase's Data API roles get
    #   nothing (this backend never uses the Data API).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'saathi_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON unanswered_questions TO saathi_app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON unanswered_questions FROM anon, authenticated;
            END IF;
        END
        $$
        """
    )


# Undo exactly the changes above (R25). In production, roll back by redeploying the previous
#   image instead: this drops the unanswered questions and FAQ vectors.
def downgrade() -> None:
    # The table (its policy and index go with it).
    op.drop_index("ix_unanswered_tenant_bot_created", table_name="unanswered_questions")
    # Drop the table.
    op.drop_table("unanswered_questions")
    # FAQ vectors.
    op.drop_column("faqs", "embedding")
    # Crawl settings.
    op.drop_column("sources", "options")
