-- migrate_add_user_llm_configs.sql
-- BYOK multi-provider LLM feature — Cactus platform
-- Run after init_db.sql is already applied.

-- ── Users (minimal — wires to Supabase auth UUID later) ───────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supabase_uid    TEXT UNIQUE,            -- Supabase auth user id, populated on first login
    vehicle_id      TEXT REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
    email_hint      VARCHAR(8),             -- first 4 + last 4 chars of email, for support only
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_supabase_uid ON users(supabase_uid);
CREATE INDEX IF NOT EXISTS idx_users_vehicle_id   ON users(vehicle_id);

-- ── BYOK LLM provider configs ─────────────────────────────────────────────────
-- encrypted_api_key: AES-256-GCM ciphertext of the user's provider API key.
-- Encryption uses CACTUS_KEY_ENCRYPTION_KEY (server-side, from k8s Secret).
-- In TEE production: decryption happens inside AMD SEV-SNP node, plaintext
-- never reaches shared GPU pool. Pre-TEE: server-side key encryption only.
CREATE TABLE IF NOT EXISTS user_llm_configs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider            VARCHAR(32) NOT NULL,           -- 'anthropic' | 'openai' | 'google'
                                                        -- | 'cohere' | 'mistral' | 'groq' | 'deepseek'
    model_id            VARCHAR(128) NOT NULL,           -- exact model string for provider API call
    encrypted_api_key   BYTEA NOT NULL,                  -- AES-256-GCM ciphertext
    key_iv              BYTEA NOT NULL,                  -- 12-byte GCM nonce for this ciphertext
    key_hint            VARCHAR(8),                      -- "...xK9f" — last 4 chars only, for UI
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    UNIQUE(user_id, provider)                            -- one config per provider per user
);

CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user_id ON user_llm_configs(user_id);

-- ── Auto-update updated_at trigger ────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_llm_configs_updated_at
    BEFORE UPDATE ON user_llm_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
