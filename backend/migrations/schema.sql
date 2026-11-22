-- =============================================================================
-- Saathi AI - full database schema (Postgres 16+ with pgvector)
--
-- GENERATED from the Alembic migrations - do not edit by hand (R25).
-- Regenerate:  make schema-sql
--
-- Normal path: `make migrate` (Alembic applies the same SQL and tracks the version).
-- Manual path (fresh, empty database only): create the saathi_app role first (see
-- infra/postgres/init/02_app_role.sh or ADR-0002), then paste this whole file into the
-- Supabase SQL Editor / psql and run it as the schema owner. It also creates the
-- alembic_version table, so `make migrate` keeps working afterwards.
-- =============================================================================

BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE EXTENSION IF NOT EXISTS vector;

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

CREATE TABLE tenants (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    plan VARCHAR(30) DEFAULT 'starter' NOT NULL, 
    monthly_token_cap INTEGER DEFAULT '2000000' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_tenants PRIMARY KEY (id), 
    CONSTRAINT ck_tenants_plan CHECK (plan IN ('starter', 'growth', 'pro')), 
    CONSTRAINT ck_tenants_monthly_token_cap CHECK (monthly_token_cap >= 0)
);

CREATE TABLE audit_logs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    actor VARCHAR(100) NOT NULL, 
    action VARCHAR(100) NOT NULL, 
    target VARCHAR(200) NOT NULL, 
    details JSONB DEFAULT '{}'::jsonb NOT NULL, 
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_audit_logs PRIMARY KEY (id), 
    CONSTRAINT fk_audit_logs_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_audit_logs_tenant_at ON audit_logs (tenant_id, at DESC);

CREATE TABLE bots (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    persona VARCHAR(2000) DEFAULT '' NOT NULL, 
    languages VARCHAR(10)[] NOT NULL, 
    public_key VARCHAR(80) NOT NULL, 
    settings JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_bots PRIMARY KEY (id), 
    CONSTRAINT ck_bots_languages CHECK (cardinality(languages) >= 1), 
    CONSTRAINT fk_bots_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_bots_public_key UNIQUE (public_key), 
    CONSTRAINT uq_bots_tenant_id_id UNIQUE (tenant_id, id), 
    CONSTRAINT uq_bots_tenant_name UNIQUE (tenant_id, name)
);

CREATE INDEX ix_bots_tenant_created ON bots (tenant_id, created_at DESC);

CREATE TABLE contacts (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    phone VARCHAR(20), 
    email VARCHAR(320), 
    name VARCHAR(200), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_contacts PRIMARY KEY (id), 
    CONSTRAINT fk_contacts_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_contacts_tenant_id_id UNIQUE (tenant_id, id)
);

CREATE UNIQUE INDEX uq_contacts_tenant_email ON contacts (tenant_id, email) WHERE email IS NOT NULL;

CREATE UNIQUE INDEX uq_contacts_tenant_phone ON contacts (tenant_id, phone) WHERE phone IS NOT NULL;

CREATE TABLE provider_credentials (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    provider VARCHAR(30) NOT NULL, 
    ciphertext TEXT NOT NULL, 
    key_last4 VARCHAR(4) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    created_by VARCHAR(100) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_provider_credentials PRIMARY KEY (id), 
    CONSTRAINT ck_provider_credentials_status CHECK (status IN ('active', 'revoked')), 
    CONSTRAINT ck_provider_credentials_key_last4 CHECK (char_length(key_last4) = 4), 
    CONSTRAINT fk_provider_credentials_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_provider_credentials_one_active ON provider_credentials (tenant_id, provider) WHERE status = 'active';

CREATE TABLE user_accounts (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    auth_user_id VARCHAR(100) NOT NULL, 
    email VARCHAR(320) NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_user_accounts PRIMARY KEY (id), 
    CONSTRAINT ck_user_accounts_role CHECK (role IN ('viewer', 'agent', 'admin', 'owner')), 
    CONSTRAINT fk_user_accounts_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_user_accounts_tenant_auth_user UNIQUE (tenant_id, auth_user_id)
);

CREATE TABLE assets (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID NOT NULL, 
    kind VARCHAR(30) NOT NULL, 
    storage_key VARCHAR(500) NOT NULL, 
    content_type VARCHAR(100) NOT NULL, 
    size_bytes INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_assets PRIMARY KEY (id), 
    CONSTRAINT ck_assets_size_bytes CHECK (size_bytes > 0), 
    CONSTRAINT fk_assets_tenant_id_bots FOREIGN KEY(tenant_id, bot_id) REFERENCES bots (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_assets_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_assets_storage_key UNIQUE (storage_key)
);

CREATE INDEX ix_assets_tenant_bot ON assets (tenant_id, bot_id);

CREATE TABLE bot_config_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    config JSONB NOT NULL, 
    created_by VARCHAR(100) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_bot_config_versions PRIMARY KEY (id), 
    CONSTRAINT ck_bot_config_versions_status CHECK (status IN ('draft', 'published', 'archived')), 
    CONSTRAINT ck_bot_config_versions_version CHECK (version >= 1), 
    CONSTRAINT fk_bot_config_versions_tenant_id_bots FOREIGN KEY(tenant_id, bot_id) REFERENCES bots (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_bot_config_versions_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_bot_config_versions_bot_version UNIQUE (bot_id, version)
);

CREATE INDEX ix_bot_config_versions_bot_status_version ON bot_config_versions (bot_id, status, version);

CREATE UNIQUE INDEX uq_bot_config_versions_one_published ON bot_config_versions (bot_id) WHERE status = 'published';

CREATE TABLE conversations (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID NOT NULL, 
    contact_id UUID, 
    channel VARCHAR(20) NOT NULL, 
    external_user_id VARCHAR(100) NOT NULL, 
    status VARCHAR(20) DEFAULT 'open' NOT NULL, 
    outcome VARCHAR(30), 
    csat SMALLINT, 
    config_version INTEGER, 
    language VARCHAR(10), 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    closed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_conversations PRIMARY KEY (id), 
    CONSTRAINT ck_conversations_channel CHECK (channel IN ('web', 'whatsapp', 'voice')), 
    CONSTRAINT ck_conversations_status CHECK (status IN ('open', 'handed_off', 'closed')), 
    CONSTRAINT ck_conversations_csat CHECK (csat IS NULL OR csat BETWEEN 1 AND 5), 
    CONSTRAINT fk_conversations_contact_id_contacts FOREIGN KEY(contact_id) REFERENCES contacts (id) ON DELETE SET NULL, 
    CONSTRAINT fk_conversations_tenant_id_bots FOREIGN KEY(tenant_id, bot_id) REFERENCES bots (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_conversations_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_conversations_tenant_id_id UNIQUE (tenant_id, id)
);

CREATE INDEX ix_conversations_tenant_bot_external_user ON conversations (tenant_id, bot_id, external_user_id);

CREATE INDEX ix_conversations_tenant_bot_last ON conversations (tenant_id, bot_id, last_message_at DESC);

CREATE TABLE faqs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID NOT NULL, 
    question VARCHAR(1000) NOT NULL, 
    answer VARCHAR(4000) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_faqs PRIMARY KEY (id), 
    CONSTRAINT fk_faqs_tenant_id_bots FOREIGN KEY(tenant_id, bot_id) REFERENCES bots (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_faqs_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_faqs_tenant_bot ON faqs (tenant_id, bot_id);

CREATE TABLE sources (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID NOT NULL, 
    kind VARCHAR(10) NOT NULL, 
    uri VARCHAR(2000) NOT NULL, 
    title VARCHAR(300), 
    status VARCHAR(20) DEFAULT 'queued' NOT NULL, 
    content_hash VARCHAR(64), 
    error VARCHAR(500), 
    synced_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_sources PRIMARY KEY (id), 
    CONSTRAINT ck_sources_kind CHECK (kind IN ('file', 'url')), 
    CONSTRAINT ck_sources_status CHECK (status IN ('queued', 'processing', 'ready', 'failed')), 
    CONSTRAINT fk_sources_tenant_id_bots FOREIGN KEY(tenant_id, bot_id) REFERENCES bots (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_sources_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_sources_tenant_bot_uri UNIQUE (tenant_id, bot_id, uri), 
    CONSTRAINT uq_sources_tenant_id_id UNIQUE (tenant_id, id)
);

CREATE INDEX ix_sources_tenant_bot_created ON sources (tenant_id, bot_id, created_at DESC);

CREATE TABLE chunks (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID NOT NULL, 
    source_id UUID NOT NULL, 
    chunk_index INTEGER NOT NULL, 
    content TEXT NOT NULL, 
    embedding VECTOR(1536) NOT NULL, 
    tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_chunks PRIMARY KEY (id), 
    CONSTRAINT ck_chunks_chunk_index CHECK (chunk_index >= 0), 
    CONSTRAINT fk_chunks_tenant_id_bots FOREIGN KEY(tenant_id, bot_id) REFERENCES bots (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_chunks_tenant_id_sources FOREIGN KEY(tenant_id, source_id) REFERENCES sources (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_chunks_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_chunks_source_index UNIQUE (source_id, chunk_index)
);

CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_chunks_tenant_bot ON chunks (tenant_id, bot_id);

CREATE INDEX ix_chunks_tsv ON chunks USING gin (tsv);

CREATE TABLE handoffs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    reason VARCHAR(100) NOT NULL, 
    summary TEXT, 
    status VARCHAR(20) DEFAULT 'requested' NOT NULL, 
    agent_id VARCHAR(100), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    resolved_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_handoffs PRIMARY KEY (id), 
    CONSTRAINT ck_handoffs_status CHECK (status IN ('requested', 'notified', 'human', 'closed', 'after_hours')), 
    CONSTRAINT fk_handoffs_tenant_id_conversations FOREIGN KEY(tenant_id, conversation_id) REFERENCES conversations (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_handoffs_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_handoffs_tenant_status_created ON handoffs (tenant_id, status, created_at);

CREATE UNIQUE INDEX uq_handoffs_one_open ON handoffs (conversation_id) WHERE status NOT IN ('closed', 'after_hours');

CREATE TABLE leads (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    contact_id UUID NOT NULL, 
    conversation_id UUID, 
    fields JSONB DEFAULT '{}'::jsonb NOT NULL, 
    crm_sync_status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_leads PRIMARY KEY (id), 
    CONSTRAINT ck_leads_crm_sync CHECK (crm_sync_status IN ('pending', 'synced', 'failed')), 
    CONSTRAINT fk_leads_conversation_id_conversations FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE SET NULL, 
    CONSTRAINT fk_leads_tenant_id_contacts FOREIGN KEY(tenant_id, contact_id) REFERENCES contacts (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_leads_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_leads_tenant_created ON leads (tenant_id, created_at DESC);

CREATE TABLE messages (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    conversation_id UUID NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    content TEXT NOT NULL, 
    citations JSONB DEFAULT '[]'::jsonb NOT NULL, 
    confidence DOUBLE PRECISION, 
    external_message_id VARCHAR(200), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_messages PRIMARY KEY (id), 
    CONSTRAINT ck_messages_role CHECK (role IN ('user', 'assistant', 'agent', 'system')), 
    CONSTRAINT ck_messages_confidence CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1), 
    CONSTRAINT fk_messages_tenant_id_conversations FOREIGN KEY(tenant_id, conversation_id) REFERENCES conversations (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_messages_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_messages_conversation_created ON messages (conversation_id, created_at);

CREATE UNIQUE INDEX uq_messages_tenant_external_id ON messages (tenant_id, external_message_id) WHERE external_message_id IS NOT NULL;

CREATE TABLE usage_logs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID, 
    message_id UUID, 
    provider VARCHAR(30) NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    tokens_in INTEGER NOT NULL, 
    tokens_out INTEGER NOT NULL, 
    cost_usd NUMERIC(12, 6) NOT NULL, 
    key_source VARCHAR(10) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_usage_logs PRIMARY KEY (id), 
    CONSTRAINT ck_usage_logs_key_source CHECK (key_source IN ('platform', 'tenant')), 
    CONSTRAINT ck_usage_logs_cost CHECK (cost_usd >= 0), 
    CONSTRAINT ck_usage_logs_tokens CHECK (tokens_in >= 0 AND tokens_out >= 0), 
    CONSTRAINT fk_usage_logs_bot_id_bots FOREIGN KEY(bot_id) REFERENCES bots (id) ON DELETE SET NULL, 
    CONSTRAINT fk_usage_logs_message_id_messages FOREIGN KEY(message_id) REFERENCES messages (id) ON DELETE SET NULL, 
    CONSTRAINT fk_usage_logs_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_usage_logs_tenant_created ON usage_logs (tenant_id, created_at);

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON tenants USING (id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE user_accounts ENABLE ROW LEVEL SECURITY;

ALTER TABLE user_accounts FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON user_accounts USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE bots ENABLE ROW LEVEL SECURITY;

ALTER TABLE bots FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON bots USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE bot_config_versions ENABLE ROW LEVEL SECURITY;

ALTER TABLE bot_config_versions FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON bot_config_versions USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

ALTER TABLE assets FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON assets USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON audit_logs USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE provider_credentials ENABLE ROW LEVEL SECURITY;

ALTER TABLE provider_credentials FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON provider_credentials USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE sources ENABLE ROW LEVEL SECURITY;

ALTER TABLE sources FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON sources USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;

ALTER TABLE chunks FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON chunks USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE faqs ENABLE ROW LEVEL SECURITY;

ALTER TABLE faqs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON faqs USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

ALTER TABLE contacts FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON contacts USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

ALTER TABLE conversations FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON conversations USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

ALTER TABLE messages FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON messages USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE handoffs ENABLE ROW LEVEL SECURITY;

ALTER TABLE handoffs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON handoffs USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

ALTER TABLE leads FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON leads USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;

ALTER TABLE usage_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON usage_logs USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

CREATE FUNCTION resolve_bot_public_key(p_key text)
        RETURNS TABLE (tenant_id uuid, bot_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT b.tenant_id, b.id FROM public.bots b WHERE b.public_key = p_key
        $$;

REVOKE ALL ON FUNCTION resolve_bot_public_key(text) FROM PUBLIC;

DO $$
        BEGIN
            -- The app role: read/write rows only, never DDL; RLS applies (NOBYPASSRLS).
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'saathi_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, user_accounts, bots, bot_config_versions, assets, audit_logs, provider_credentials, sources, chunks, faqs, contacts, conversations, messages, handoffs, leads, usage_logs TO saathi_app;
                -- Audit trail is append-only for the app.
                REVOKE UPDATE, DELETE ON audit_logs FROM saathi_app;
                -- Only migrations may touch the migration bookkeeping.
                IF to_regclass('public.alembic_version') IS NOT NULL THEN
                    REVOKE ALL ON alembic_version FROM saathi_app;
                END IF;
                GRANT EXECUTE ON FUNCTION resolve_bot_public_key(text) TO saathi_app;
            END IF;

            -- Supabase exposes the public schema through its Data API and grants these roles
            -- access by default. This backend never uses the Data API: take that access away.
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON tenants, user_accounts, bots, bot_config_versions, assets, audit_logs, provider_credentials, sources, chunks, faqs, contacts, conversations, messages, handoffs, leads, usage_logs FROM anon, authenticated;
                REVOKE ALL ON FUNCTION resolve_bot_public_key(text) FROM anon, authenticated;
                IF to_regclass('public.alembic_version') IS NOT NULL THEN
                    REVOKE ALL ON alembic_version FROM anon, authenticated;
                END IF;
            END IF;
        END
        $$;

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

CREATE INDEX ix_user_accounts_auth_user_id ON user_accounts (auth_user_id);

CREATE FUNCTION resolve_user_membership(p_auth_user_id text)
        RETURNS TABLE (tenant_id uuid, role text)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT u.tenant_id, u.role::text
            FROM public.user_accounts u
            WHERE u.auth_user_id = p_auth_user_id
            ORDER BY u.created_at
        $$;

REVOKE ALL ON FUNCTION resolve_user_membership(text) FROM PUBLIC;

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
        $$;

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

-- Running upgrade 0003 -> 0004

ALTER TABLE sources ADD COLUMN options JSONB;

ALTER TABLE faqs ADD COLUMN embedding VECTOR(1536);

CREATE TABLE unanswered_questions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    tenant_id UUID NOT NULL, 
    bot_id UUID NOT NULL, 
    conversation_id UUID, 
    question VARCHAR(2000) NOT NULL, 
    language VARCHAR(10) NOT NULL, 
    reason VARCHAR(30) NOT NULL, 
    top_score DOUBLE PRECISION, 
    config_version INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_unanswered_questions PRIMARY KEY (id), 
    CONSTRAINT ck_unanswered_questions_reason CHECK (reason IN ('no_results', 'low_confidence', 'unsupported', 'provider_unavailable')), 
    CONSTRAINT fk_unanswered_questions_tenant_id_bots FOREIGN KEY(tenant_id, bot_id) REFERENCES bots (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_unanswered_questions_tenant_id_conversations FOREIGN KEY(tenant_id, conversation_id) REFERENCES conversations (tenant_id, id) ON DELETE CASCADE, 
    CONSTRAINT fk_unanswered_questions_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_unanswered_tenant_bot_created ON unanswered_questions (tenant_id, bot_id, created_at DESC);

ALTER TABLE unanswered_questions ENABLE ROW LEVEL SECURITY;

ALTER TABLE unanswered_questions FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON unanswered_questions USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'saathi_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON unanswered_questions TO saathi_app;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON unanswered_questions FROM anon, authenticated;
            END IF;
        END
        $$;

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

COMMIT;

