-- =============================================================================
-- Cadence: Full Schema (Fresh Start)
-- =============================================================================
-- Run this file on a fresh (or dropped) database to create the complete schema
-- including all tables, indexes, and seed data.
--
--   psql -U <user> -d <db> -f migrations/schema.sql
--
-- This replaces the incremental Alembic migrations. Alembic is no longer used.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE
EXTENSION IF NOT EXISTS "pgcrypto";


-- ---------------------------------------------------------------------------
-- DROP all tables (cascade handles FK order)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS user_org_memberships CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS orchestrator_instances CASCADE;
DROP TABLE IF EXISTS organization_llm_configs CASCADE;
DROP TABLE IF EXISTS organization_settings CASCADE;
DROP TABLE IF EXISTS org_plugins CASCADE;
DROP TABLE IF EXISTS system_plugins CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;
DROP TABLE IF EXISTS global_settings CASCADE;
DROP TABLE IF EXISTS provider_model_configs CASCADE;


-- ---------------------------------------------------------------------------
-- global_settings
-- ---------------------------------------------------------------------------
CREATE TABLE global_settings
(
    id          SERIAL PRIMARY KEY,
    key         VARCHAR(255) NOT NULL UNIQUE,
    value       JSONB        NOT NULL,
    value_type  VARCHAR(50)  NOT NULL,
    description TEXT,
    overridable BOOLEAN      NOT NULL DEFAULT FALSE,
    category    VARCHAR(50),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(255),
    updated_by  VARCHAR(255),
    is_deleted  BOOLEAN      NOT NULL DEFAULT FALSE
);


-- ---------------------------------------------------------------------------
-- organizations
-- ---------------------------------------------------------------------------
CREATE TABLE organizations
(
    id                UUID PRIMARY KEY      DEFAULT gen_random_uuid(),
    name              VARCHAR(255) NOT NULL,
    status            VARCHAR(50)  NOT NULL DEFAULT 'active',
    display_name      VARCHAR(500),
    domain            VARCHAR(255) NOT NULL,
    subscription_tier VARCHAR(50)  NOT NULL DEFAULT 'free',
    description       TEXT,
    contact_email     VARCHAR(255),
    website           VARCHAR(500),
    logo_url          VARCHAR(1000),
    country           VARCHAR(100),
    timezone          VARCHAR(100),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by        VARCHAR(255),
    updated_by        VARCHAR(255),
    is_deleted        BOOLEAN      NOT NULL DEFAULT FALSE
);

-- Unique index: domain is required and must be globally unique
CREATE UNIQUE INDEX uq_org_domain ON organizations (domain);


-- ---------------------------------------------------------------------------
-- organization_settings
-- ---------------------------------------------------------------------------
CREATE TABLE organization_settings
(
    id          SERIAL PRIMARY KEY,
    org_id      UUID         NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    key         VARCHAR(255) NOT NULL,
    value       JSONB        NOT NULL,
    overridable BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(255),
    updated_by  VARCHAR(255),
    is_deleted  BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_org_setting_key UNIQUE (org_id, key)
);

CREATE INDEX idx_org_settings_org_id ON organization_settings (org_id);


-- ---------------------------------------------------------------------------
-- organization_llm_configs
-- ---------------------------------------------------------------------------
CREATE TABLE organization_llm_configs
(
    id                SERIAL PRIMARY KEY,
    org_id            UUID         NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    name              VARCHAR(255) NOT NULL,
    provider          VARCHAR(50)  NOT NULL,
    api_key           TEXT         NOT NULL,
    base_url          VARCHAR(512),
    additional_config JSONB,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ,
    created_by        VARCHAR(255),
    updated_by        VARCHAR(255),
    is_deleted        BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX uq_org_llm_config_name_active
    ON organization_llm_configs (org_id, name) WHERE is_deleted = FALSE;

CREATE UNIQUE INDEX uq_org_llm_config_provider_key_active
    ON organization_llm_configs (org_id, provider, api_key) WHERE is_deleted = FALSE;

CREATE INDEX idx_org_llm_configs_org_id ON organization_llm_configs (org_id);


-- ---------------------------------------------------------------------------
-- orchestrator_instances
-- ---------------------------------------------------------------------------
CREATE TABLE orchestrator_instances
(
    id               UUID PRIMARY KEY      DEFAULT gen_random_uuid(),
    org_id           UUID         NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    name             VARCHAR(255) NOT NULL,
    framework_type   VARCHAR(50)  NOT NULL,
    mode             VARCHAR(50)  NOT NULL,
    status           VARCHAR(50)  NOT NULL DEFAULT 'active',
    config           JSONB        NOT NULL DEFAULT '{}',
    tier             VARCHAR(20)  NOT NULL DEFAULT 'cold',
    plugin_settings  JSONB,
    config_hash      VARCHAR(64),
    last_accessed_at TIMESTAMPTZ           DEFAULT NOW(),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       VARCHAR(255),
    updated_by       VARCHAR(255),
    is_deleted       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_orchestrator_instances_org_id ON orchestrator_instances (org_id);
CREATE INDEX idx_orchestrator_instances_status ON orchestrator_instances (org_id, status);
CREATE INDEX idx_orchestrator_instances_last_accessed ON orchestrator_instances (last_accessed_at);
CREATE INDEX idx_orchestrator_instances_tier ON orchestrator_instances (tier);


-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE users
(
    id            UUID PRIMARY KEY      DEFAULT gen_random_uuid(),
    username      VARCHAR(255) NOT NULL,
    email         VARCHAR(255),
    password_hash TEXT,
    is_sys_admin  BOOLEAN      NOT NULL DEFAULT FALSE,
    display_name  VARCHAR(255),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ,
    created_by    VARCHAR(255),
    updated_by    VARCHAR(255),
    is_deleted    BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX uq_user_username_active ON users (username) WHERE is_deleted = FALSE;
CREATE UNIQUE INDEX uq_user_email_active ON users (email) WHERE is_deleted = FALSE AND email IS NOT NULL;


-- ---------------------------------------------------------------------------
-- user_org_memberships
-- ---------------------------------------------------------------------------
CREATE TABLE user_org_memberships
(
    id         SERIAL PRIMARY KEY,
    user_id    UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    org_id     UUID        NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    is_admin   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    CONSTRAINT uq_user_org_membership UNIQUE (user_id, org_id)
);

CREATE INDEX idx_user_org_mem_user_id ON user_org_memberships (user_id);
CREATE INDEX idx_user_org_mem_org_id ON user_org_memberships (org_id);


-- ---------------------------------------------------------------------------
-- system_plugins
-- ---------------------------------------------------------------------------
CREATE TABLE system_plugins
(
    id               UUID PRIMARY KEY      DEFAULT gen_random_uuid(),
    pid              VARCHAR(255) NOT NULL,
    version          VARCHAR(50)  NOT NULL,
    name             VARCHAR(255) NOT NULL,
    description      TEXT,
    tag              VARCHAR(100),
    is_latest        BOOLEAN      NOT NULL DEFAULT FALSE,
    s3_path          VARCHAR(512),
    default_settings JSONB,
    capabilities     JSONB,
    agent_type       VARCHAR(50)  NOT NULL DEFAULT 'specialized',
    stateless        BOOLEAN      NOT NULL DEFAULT TRUE,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ,
    created_by       VARCHAR(255),
    updated_by       VARCHAR(255),
    CONSTRAINT uq_system_plugin_pid_version UNIQUE (pid, version)
);

CREATE INDEX idx_system_plugins_pid ON system_plugins (pid);

CREATE UNIQUE INDEX uq_system_plugin_latest ON system_plugins (pid) WHERE is_latest = TRUE;


-- ---------------------------------------------------------------------------
-- org_plugins
-- ---------------------------------------------------------------------------
CREATE TABLE org_plugins
(
    id               UUID PRIMARY KEY      DEFAULT gen_random_uuid(),
    org_id           UUID         NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    pid              VARCHAR(255) NOT NULL,
    version          VARCHAR(50)  NOT NULL,
    name             VARCHAR(255) NOT NULL,
    description      TEXT,
    tag              VARCHAR(100),
    is_latest        BOOLEAN      NOT NULL DEFAULT FALSE,
    s3_path          VARCHAR(512),
    default_settings JSONB,
    capabilities     JSONB,
    agent_type       VARCHAR(50)  NOT NULL DEFAULT 'specialized',
    stateless        BOOLEAN      NOT NULL DEFAULT TRUE,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ,
    created_by       VARCHAR(255),
    updated_by       VARCHAR(255),
    CONSTRAINT uq_org_plugin_org_pid_version UNIQUE (org_id, pid, version)
);

CREATE INDEX idx_org_plugins_catalog_org_id ON org_plugins (org_id);

CREATE UNIQUE INDEX uq_org_plugin_latest ON org_plugins (org_id, pid) WHERE is_latest = TRUE;


-- ---------------------------------------------------------------------------
-- provider_model_configs
-- ---------------------------------------------------------------------------
CREATE TABLE provider_model_configs
(
    id           SERIAL PRIMARY KEY,
    provider     VARCHAR(50)  NOT NULL,
    model_id     VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    aliases      JSONB        NOT NULL DEFAULT '[]',
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_provider_model_id_active
    ON provider_model_configs (provider, model_id) WHERE is_active = TRUE;

CREATE INDEX idx_provider_model_configs_provider ON provider_model_configs (provider);


-- ---------------------------------------------------------------------------
-- conversations
-- ---------------------------------------------------------------------------
CREATE TABLE conversations
(
    id          UUID PRIMARY KEY     DEFAULT gen_random_uuid(),
    title       VARCHAR(500),
    org_id      UUID        NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    user_id     UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    instance_id UUID        REFERENCES orchestrator_instances (id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ,
    created_by  VARCHAR(255),
    updated_by  VARCHAR(255),
    is_deleted  BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_conversations_user_id ON conversations (user_id);
CREATE INDEX idx_conversations_instance_id ON conversations (instance_id);
CREATE INDEX idx_conversations_org_id ON conversations (org_id);


-- =============================================================================
-- SEED: provider_model_configs
-- =============================================================================
INSERT INTO provider_model_configs (provider, model_id, display_name, aliases, is_active, created_at, updated_at)
VALUES
    -- OpenAI Chat
    ('openai', 'gpt-4o', 'GPT-4o', '[
      "4o"
    ]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-4.1', 'GPT-4.1', '[
      "4.1"
    ]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-4.1-mini', 'GPT-4.1 Mini', '[
      "4.1-mini"
    ]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-4.1-nano', 'GPT-4.1 Nano', '[
      "4.1-nano"
    ]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-4.5-preview-2025-02-27', 'GPT-4.5 Preview (2025-02-27)', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-4.5-preview', 'GPT-4.5 Preview', '[
      "gpt-4.5"
    ]', TRUE, NOW(), NOW()),
    ('openai', 'o1-mini', 'o1 Mini', '[]', TRUE, NOW(), NOW()),
    ('openai', 'o3-mini', 'o3 Mini', '[]', TRUE, NOW(), NOW()),
    ('openai', 'o3', 'o3', '[]', TRUE, NOW(), NOW()),
    ('openai', 'o4-mini', 'o4 Mini', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5', 'GPT-5', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5-mini', 'GPT-5 Mini', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5-nano', 'GPT-5 Nano', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5-2025-08-07', 'GPT-5 (2025-08-07)', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5-mini-2025-08-07', 'GPT-5 Mini (2025-08-07)', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5-nano-2025-08-07', 'GPT-5 Nano (2025-08-07)', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5.1', 'GPT-5.1', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5.1-chat-latest', 'GPT-5.1 Chat Latest', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5.2', 'GPT-5.2', '[]', TRUE, NOW(), NOW()),
    ('openai', 'gpt-5.2-chat-latest', 'GPT-5.2 Chat Latest', '[]', TRUE, NOW(), NOW()),
    -- Anthropic
    ('anthropic', 'claude-opus-4-6', 'Claude Opus 4.6', '[]', TRUE, NOW(), NOW()),
    ('anthropic', 'claude-sonnet-4-6', 'Claude Sonnet 4.6', '[]', TRUE, NOW(), NOW()),
    ('anthropic', 'claude-haiku-4-5-20251001', 'Claude Haiku 4.5', '[]', TRUE, NOW(), NOW()),
    -- Google
    ('google', 'gemini-3.1-pro-preview', 'Gemini 3.0 Pro Preview', '[]', TRUE, NOW(), NOW()),
    ('google', 'gemini-3-flash-preview', 'Gemini 3.0 Flash Preview', '[]', TRUE, NOW(), NOW()),
    ('google', 'gemini-3.1-flash-lite', 'Gemini 3.1 Flash Lite', '[]', TRUE, NOW(), NOW()),
    ('google', 'gemini-2.5-pro', 'Gemini 2.5 Pro', '[]', TRUE, NOW(), NOW()),
    ('google', 'gemini-2.5-flash', 'Gemini 2.5 Flash', '[]', TRUE, NOW(), NOW()),
    ('google', 'gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite', '[]', TRUE, NOW(), NOW()),
    -- Groq
    ('groq', 'qwen/qwen3-32b', 'Alibaba Qwen3 32B', '[]', TRUE, NOW(), NOW()),
    ('groq', 'groq/compound', 'Groq Compound', '[]', TRUE, NOW(), NOW()),
    ('groq', 'groq/compound-mini', 'Groq Compound Mini', '[]', TRUE, NOW(), NOW()),
    ('groq', 'llama-3.1-8b-instant', 'Meta Llama 3.1 8B Instant', '[]', TRUE, NOW(), NOW()),
    ('groq', 'llama-3.3-70b-versatile', 'Meta Llama 3.3 70B Versatile', '[]', TRUE, NOW(), NOW()),
    ('groq', 'meta-llama/llama-4-scout-17b-16e-instruct', 'Meta Llama 4.4 Scout 17B 16e Instruct', '[]', TRUE, NOW(),
     NOW()),
    ('groq', 'moonshotai/kimi-k2-instruct-0905', 'MoonshotAI Kimi K2 Instruct', '[]', TRUE, NOW(), NOW()),
    ('groq', 'openai/gpt-oss-120b', 'GPT OSS 120B', '[]', TRUE, NOW(), NOW()),
    ('groq', 'openai/gpt-oss-20b', 'GPT OSS 20B', '[]', TRUE, NOW(), NOW()),
    ('groq', 'openai/gpt-oss-safeguard-20b', 'GPT OSS SafeGuard 20B', '[]', TRUE, NOW(), NOW()) ON CONFLICT DO NOTHING;


-- =============================================================================
-- SEED: global_settings — subscription tier definitions (category='tier')
-- =============================================================================
INSERT INTO global_settings (key, value, value_type, description, overridable, category, created_at, updated_at,
                             is_deleted)
VALUES ('tier.free',
        '{
          "max_orchestrators": 1,
          "max_members": 3,
          "max_messages_per_month": 500,
          "max_messages_per_day": 50,
          "rate_limit_rpm": 10,
          "rate_limit_burst": 20,
          "max_llm_configs": 1,
          "description": "Free tier"
        }'::jsonb,
        'object', 'Quota limits for the free subscription tier', FALSE, 'tier', NOW(), NOW(), FALSE),
       ('tier.plus',
        '{
          "max_orchestrators": 3,
          "max_members": 10,
          "max_messages_per_month": 5000,
          "max_messages_per_day": 500,
          "rate_limit_rpm": 30,
          "rate_limit_burst": 60,
          "max_llm_configs": 3,
          "description": "Plus tier"
        }'::jsonb,
        'object', 'Quota limits for the plus subscription tier', FALSE, 'tier', NOW(), NOW(), FALSE),
       ('tier.pro',
        '{
          "max_orchestrators": 10,
          "max_members": 25,
          "max_messages_per_month": 25000,
          "max_messages_per_day": 2500,
          "rate_limit_rpm": 60,
          "rate_limit_burst": 120,
          "max_llm_configs": 10,
          "description": "Pro tier"
        }'::jsonb,
        'object', 'Quota limits for the pro subscription tier', FALSE, 'tier', NOW(), NOW(), FALSE),
       ('tier.premium',
        '{
          "max_orchestrators": 25,
          "max_members": 100,
          "max_messages_per_month": 100000,
          "max_messages_per_day": 10000,
          "rate_limit_rpm": 120,
          "rate_limit_burst": 240,
          "max_llm_configs": 25,
          "description": "Premium tier"
        }'::jsonb,
        'object', 'Quota limits for the premium subscription tier', FALSE, 'tier', NOW(), NOW(), FALSE),
       ('tier.business',
        '{
          "max_orchestrators": 100,
          "max_members": 500,
          "max_messages_per_month": 500000,
          "max_messages_per_day": 50000,
          "rate_limit_rpm": 300,
          "rate_limit_burst": 600,
          "max_llm_configs": 100,
          "description": "Business tier"
        }'::jsonb,
        'object', 'Quota limits for the business subscription tier', FALSE, 'tier', NOW(), NOW(), FALSE),
       ('tier.enterprise',
        '{
          "max_orchestrators": -1,
          "max_members": -1,
          "max_messages_per_month": -1,
          "max_messages_per_day": -1,
          "rate_limit_rpm": 1000,
          "rate_limit_burst": 2000,
          "max_llm_configs": -1,
          "description": "Enterprise tier — unlimited"
        }'::jsonb,
        'object', 'Quota limits for the enterprise subscription tier (-1 = unlimited)', FALSE, 'tier', NOW(), NOW(),
        FALSE) ON CONFLICT (key) DO NOTHING;
