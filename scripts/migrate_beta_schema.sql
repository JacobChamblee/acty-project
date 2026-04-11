-- migrate_beta_schema.sql
-- Beta schema fixes for Acty/Cactus platform
-- Run AFTER init_db.sql and migrate_add_user_llm_configs.sql are already applied.
--
-- Apply with:
--   psql $DATABASE_URL < scripts/migrate_beta_schema.sql
-- or inside the postgres container:
--   docker exec -i acty-postgres psql -U acty -d acty-postgres < scripts/migrate_beta_schema.sql

-- ── Fix 1: Add owner_id to vehicles ───────────────────────────────────────────
-- Links every vehicle to the Supabase-authenticated user who owns it.
-- Without this, session queries cannot be scoped to a user — root cause of the
-- web ↔ Android data loss problem.

ALTER TABLE vehicles
  ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_vehicles_owner_id ON vehicles(owner_id);

-- ── Fix 2: Remove vehicle_id from users ───────────────────────────────────────
-- The old schema had a single vehicle_id FK on users, which is wrong — one user
-- can own multiple vehicles. Ownership is now tracked via vehicles.owner_id.
-- Safe to drop because vehicle ownership is now on vehicles.owner_id.

ALTER TABLE users DROP COLUMN IF EXISTS vehicle_id;

-- ── Fix 3: OBD adapter registry ───────────────────────────────────────────────
-- Stores discovered BT adapters per user/vehicle so the app can reconnect
-- automatically and know which PID set to use per adapter.

CREATE TABLE IF NOT EXISTS obd_adapters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vehicle_id      TEXT REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
    mac_address     TEXT NOT NULL,
    adapter_name    TEXT,
    adapter_type    TEXT,           -- 'vgate_icar_pro_2s' | 'veepeak_ble' | 'vgate_ble_4'
                                    -- | 'bafx' | 'obdlink_cx' | 'unknown'
    bt_version      TEXT,           -- '5.2 BLE' | '4.0 BLE' | '3.0 SPP' | '5.1 BLE'
    supported_pids  TEXT[],         -- cached from last successful probe
    pid_mode        TEXT,           -- 'full_probe' | 'basic_12'
    is_default      BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(owner_id, mac_address)
);

CREATE INDEX IF NOT EXISTS idx_obd_adapters_owner_id   ON obd_adapters(owner_id);
CREATE INDEX IF NOT EXISTS idx_obd_adapters_vehicle_id ON obd_adapters(vehicle_id);

-- Auto-update updated_at on obd_adapters (reuse trigger function from migration)
CREATE TRIGGER trg_obd_adapters_updated_at
    BEFORE UPDATE ON obd_adapters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Fix 4: Ensure session_rows table exists ───────────────────────────────────
-- The MCP server references session_rows for per-PID time-series queries.
-- Add if not already present from init_db.sql.

CREATE TABLE IF NOT EXISTS session_rows (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp   TIMESTAMPTZ NOT NULL,
    elapsed_s   NUMERIC(10,3),
    pid_values  JSONB NOT NULL DEFAULT '{}'::jsonb,
    record_hash TEXT,
    prev_hash   TEXT,
    seq         INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_rows_session_id  ON session_rows(session_id);
CREATE INDEX IF NOT EXISTS idx_session_rows_timestamp   ON session_rows(timestamp DESC);

-- ── Fix 5: Add default vehicle if missing (for existing sessions) ─────────────
-- The server currently persists sessions with vehicle_id = 'default'.
-- Ensure a row exists so FK constraint is satisfied.

INSERT INTO vehicles (vehicle_id, make, model, year, engine)
VALUES ('default', 'Toyota', 'GR86', 2023, 'FA24')
ON CONFLICT (vehicle_id) DO NOTHING;

-- ── Fix 6: PostgreSQL-backed insights job store ──────────────────────────────
-- Replaces the in-memory asyncio.Queue store with a durable table.
-- Metadata (provider, model, status) persisted for observability and recovery.
-- Active token streaming still uses in-memory queues on the same instance;
-- this table is the source-of-truth for job lifecycle and completion.

CREATE TABLE IF NOT EXISTS jobs (
    id          UUID PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    vehicle_id  TEXT REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
    provider    TEXT NOT NULL,
    model_id    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | running | complete | error
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_user_id   ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status    ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created   ON jobs(created_at DESC);

-- Auto-update updated_at
CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Verification ──────────────────────────────────────────────────────────────
-- Run this query after migration to confirm all tables exist:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' ORDER BY table_name;
--
-- Expected tables:
--   alerts, anomaly_results, app_user_accounts, diagnostic_reports,
--   jobs, maintenance_predictions, obd_adapters, ollama_analyses,
--   session_rows, sessions, user_llm_configs, users, vehicles
