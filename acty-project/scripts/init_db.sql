-- init_db.sql
-- Acty database schema
-- Auto-runs on first postgres container start

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── Vehicles ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vehicles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id      TEXT UNIQUE NOT NULL,       -- pseudonymous ZK token
    make            TEXT,
    model           TEXT,
    year            INTEGER,
    engine          TEXT,
    vin_hash        TEXT,                       -- SHA-256 of VIN, never raw VIN
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── OBD Sessions ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id      TEXT REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    session_date    DATE,
    session_time    TIME,
    duration_min    NUMERIC(8,2),
    sample_count    INTEGER,
    avg_rpm         NUMERIC(8,2),
    max_rpm         NUMERIC(8,2),
    avg_speed_kmh   NUMERIC(8,2),
    max_speed_kmh   NUMERIC(8,2),
    avg_coolant_c   NUMERIC(8,2),
    max_coolant_c   NUMERIC(8,2),
    avg_engine_load NUMERIC(8,2),
    ltft_b1         NUMERIC(8,4),
    stft_b1         NUMERIC(8,4),
    avg_timing      NUMERIC(8,4),
    avg_maf         NUMERIC(8,4),
    pct_time_moving NUMERIC(8,2),
    fuel_level_pct  NUMERIC(8,2),
    battery_v       NUMERIC(8,4),
    health_score    INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Anomaly Results ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS anomaly_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    vehicle_id      TEXT,
    method          TEXT NOT NULL,              -- isolation_forest | lstm_autoencoder
    anomaly_score   NUMERIC(8,4),
    is_anomaly      BOOLEAN,
    flagged_pids    TEXT[],
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Maintenance Predictions ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID REFERENCES sessions(id) ON DELETE CASCADE,
    vehicle_id          TEXT,
    target              TEXT NOT NULL,
    label               TEXT,
    health_score        NUMERIC(8,4),
    stress_score        NUMERIC(8,4),
    severity            TEXT,                   -- normal | warning | critical
    confidence          NUMERIC(8,4),
    contributing_pids   TEXT[],
    recommendation      TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── Diagnostic Reports ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diagnostic_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    vehicle_id      TEXT,
    dtc_codes       TEXT[],
    anomaly_count   INTEGER,
    rag_query       TEXT,
    rag_grounded    BOOLEAN DEFAULT FALSE,
    report_text     TEXT,
    model_used      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Alerts ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID REFERENCES sessions(id) ON DELETE CASCADE,
    vehicle_id  TEXT,
    pid         TEXT,
    label       TEXT,
    severity    TEXT,
    value       NUMERIC(12,4),
    unit        TEXT,
    message     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sessions_vehicle_id   ON sessions(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at   ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_session_id    ON anomaly_results(session_id);
CREATE INDEX IF NOT EXISTS idx_maint_vehicle_id      ON maintenance_predictions(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_reports_vehicle_id    ON diagnostic_reports(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_alerts_session_id     ON alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity       ON alerts(severity);
