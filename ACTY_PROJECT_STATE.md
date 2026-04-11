# Acty / Cactus — Project State Document
> Generated: April 2026 | For Claude evaluation and onboarding
> Cross-reference: `CACTUS_MCP_CLAUDE_CODE_CONTEXT.md` for infrastructure reference

---

## 1. What This Is

**Cactus** (consumer app name) / **Acty** (platform brand) is a privacy-first OBD-II vehicle telemetry platform. Revenue model: hardware sales + verified report fees. Not data brokerage.

**Core value prop:** Owner-encrypted data → tamper-evident signed reports → ML diagnostics → no data selling.

**Company:** Acty Labs LLC, Texas single-member LLC. DBA "Cactus" filed in Williamson County.

### Live surfaces
| Surface | URL | Status |
|---|---|---|
| Web app | `cactus-app.io` (Cloudflare Pages) | Deployed, auto-deploys from `main` |
| API | `api.acty-labs.com` | Live, behind Caddy on CM3588 |
| Verify endpoint | `https://verify.acty-labs.com/verify/<session_id>` | Live |

---

## 2. Infrastructure

| Host | IP | Role |
|---|---|---|
| 4U DIY Server | `192.168.68.138` | FastAPI (8765), RAG (8766), Ollama (11434), PostgreSQL (5432), Grafana (3000), MCP (8767) |
| CM3588 | `192.168.68.121` | Caddy reverse proxy, Ed25519 signing service |
| TrueNAS | `192.168.68.125` | CSV archive, SMB share1 |
| Dell R7525 | `192.168.68.220` iDRAC | Future ML training (blocked — PSP fault) |

**4U server:** Ubuntu 24.04, i5-10400, RTX 3060 12GB, ~16GB RAM.
**CM3588:** Xubuntu 22.04 aarch64, 8-core, 8GB RAM.

**Docker services on 4U:**
- `acty-api` — FastAPI backend
- `acty-postgres` — PostgreSQL 16 (init via `scripts/init_db.sql`)
- `acty-grafana` — Grafana monitoring

**Not in Docker (native on 4U):** Ollama, RAG server (port 8766), MCP server (port 8767)

---

## 3. Architecture & Data Flow

```
[VeePeak BLE Dongle] ─── Bluetooth SPP ───► [Android App / Python Script]
                                                     │
                                               CSV + Ed25519 sig
                                                     │
                                            POST /api/v1/sessions/sync
                                                     │
                                          [FastAPI — port 8765]
                                           │             │
                                     PostgreSQL      ML Pipeline
                                     (persist)    (anomaly, predictive)
                                           │             │
                                    POST /api/v1/insights/generate
                                           │
                                    ┌──────┴──────┐
                                    │             │
                                 RAG server    LLM Provider
                                 (port 8766)   (BYOK or Ollama fallback)
                                 ChromaDB +    deepseek-r1:14b /
                                 FSM manuals   llama3.1:8b
                                    │             │
                                    └──────┬──────┘
                                    SSE stream to frontend
                                           │
                              [React web / Android InsightsScreen]
```

**MCP server** (port 8767) runs alongside on 4U — gives Claude Code direct DB + API access for diagnostics.

---

## 4. Backend API — Full Endpoint Map

**File:** `backend/api/server.py` + `backend/api/routers/`
**Port:** 8765 | **Framework:** FastAPI + asyncpg

### Core endpoints (server.py)

| Method | Path | Auth | DB | Purpose |
|---|---|---|---|---|
| GET | `/` | None | No | Root |
| GET | `/health` | None | Yes | Uptime + DB ping |
| GET | `/sessions` | None | No | List CSV files on disk |
| GET | `/sessions/{filename}` | None | No | Full analysis for one session |
| POST | `/upload` | None | Yes | CSV upload → analysis → persist |
| GET | `/insights` | None | Yes | Session insight (summary + alerts + sparklines) |
| POST | `/api/v1/report` | None | Yes | RAG-grounded diagnostic report |
| GET | `/app` | None | No | Serves `web/index.html` |

### Router: `/api/v1/auth/` (`routers/auth.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/register` | None | Create account in `app_user_accounts` |
| POST | `/login` | None | Password comparison, returns account JSON |
| POST | `/sync` | None | Upsert account across web/Android |
| POST | `/lookup` | None | Get account by email |
| GET | `/me` | JWT | Return Supabase user profile |

⚠️ **Issue:** Password stored as hash string compared with plain `==` — no salt, timing attack vulnerable. Designed for prototype.

### Router: `/api/v1/insights/` (`routers/insights.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/generate` | Optional JWT | Start LLM insight job → returns `{job_id}` immediately (202) |
| GET | `/stream/{job_id}` | None | SSE token stream |
| GET | `/job/{job_id}/status` | None | JSON poll fallback |

**Flow:** Builds `CactusPrompt` from DB + RAG → submits to BYOK provider → streams to SSE → falls back to Ollama on failure.

⚠️ **Issue:** Job store is `in-memory asyncio.Queue` — jobs lost on restart. Needs Redis for production.

### Router: `/api/v1/llm-config/` (`routers/llm_config.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/providers` | None | List all 7 supported providers + models |
| POST | `/` | JWT | Register encrypted API key |
| GET | `/` | JWT | List user's active configs (hint only, never plaintext) |
| DELETE | `/{provider}` | JWT | Remove provider config |
| POST | `/{provider}/validate` | JWT | Validate key (currently disabled — TODO) |

**Encryption:** AES-256-GCM, key from `CACTUS_KEY_ENCRYPTION_KEY`. `encrypt_api_key()` / `decrypt_api_key()` in `backend/llm/key_encryption.py`.

### Router: `/api/v1/ollama/` (`routers/ollama_router.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/models` | List models on Ollama at 192.168.68.138:11434 |
| POST | `/analyze` | Read CSV, run rule engine, stream Ollama analysis via SSE |

### Router: `/api/v1/sessions/` (`routers/sessions_router.py`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/sync` | Android SyncManager upload (base64 CSV + sig) |
| GET | `/` | List sessions (forward to /sessions) |

---

## 5. ML Pipeline

**Directory:** `backend/ml/pipeline/`

| Stage | File | Status |
|---|---|---|
| 1 | `obd_normalize.py` | PID normalization, unit conversion |
| 2 | `anomaly.py` | Isolation Forest (200 estimators, 5% contamination) on 11 PID columns → anomaly_score, flagged_pids |
| 3 | `predictive.py` | XGBoost + Random Forest ensemble, 5 maintenance targets (oil, fuel, cooling, ignition, battery/alternator) |
| 4 | `battery_health.py` | Voltage-based battery health |
| 5 | `oil_change_detector.py` | Oil change event detection |
| 6 | `oil_interval_advisor.py` | Service interval recommendations |
| 7 | `oil_level_estimator.py` | Oil level estimation from PIDs |
| 8 | `maintenance_tracker.py` | Maintenance interval tracking |
| 9 | `report.py` | RAG query + Ollama streaming → `diagnostic_reports` table |

**Maintenance targets (predictive.py):**
- `oil_degradation` — ENGINE_OIL_TEMP, RPM, ENGINE_LOAD, COOLANT_TEMP
- `fuel_system_stress` — SHORT/LONG FUEL TRIM, MAF, RPM
- `cooling_system_stress` — COOLANT_TEMP, ENGINE_LOAD, RPM, INTAKE_TEMP
- `ignition_health` — TIMING_ADVANCE, RPM, ENGINE_LOAD, SHORT_FUEL_TRIM
- `battery_alternator` — CONTROL_VOLTAGE, RPM, ENGINE_LOAD

**Not yet implemented:** LSTM autoencoder (Tier 4), fleet learning (Tier 5).

---

## 6. RAG Server

**File:** `backend/ml/rag/server/rag_server.py`
**Port:** 8766 | Runs natively on 4U (systemd)

**Endpoints:**
- `GET /health`
- `POST /retrieve` — ChromaDB similarity search `{query, top_k}` → `{chunks: [{source, page, text, distance}]}`
- `POST /context` — Returns formatted context string
- `POST /query` — Full pipeline: retrieve + Ollama generation `{query, top_k, model}` → `{answer, sources}`

**Data source:** GR86/BRZ Factory Service Manuals (PDF), processed via 5-script pipeline:
- `01_parse_fsm.py` — PDF extraction (pdfplumber + pymupdf + pytesseract OCR)
- `02_embed.py` — Embeddings via `BAAI/bge-large-en-v1.5` / `nomic-embed-text`
- `03_query.py` — Query logic
- `04_acty_bridge.py` — Integration bridge

**Called from:** `insights.py` with 8s timeout; degrades gracefully if unreachable.

---

## 7. LLM Providers (BYOK System)

**Directory:** `backend/llm/`

| Provider | File | Default Model | Cost/1M tok (in/out) |
|---|---|---|---|
| Anthropic | `anthropic.py` | claude-3-5-sonnet-20241022 | $3 / $15 |
| OpenAI | `openai_provider.py` | gpt-4o | $10 / $30 |
| Google | `google.py` | gemini-2.0-flash | Free tier |
| Cohere | `cohere.py` | command-r-plus | — |
| Mistral | `mistral.py` | mistral-large | — |
| Groq | `groq_provider.py` | llama3-70b-versatile | — |
| DeepSeek | `deepseek.py` | deepseek-chat | — |
| **Fallback** | `fallback.py` | deepseek-r1:14b (local Ollama) | Free |

All providers implement `async stream_insight(prompt: CactusPrompt, model_id, api_key)` → yields tokens.

**Fallback logic:** If BYOK key missing or provider fails mid-stream → silently switches to local Ollama.

**CactusPrompt fields:**
```python
vehicle_context:       {make, model, year, engine, odometer_km}
session_summary:       {date, duration, drive_type, PID aggregates}
ltft_trend:            {n_sessions, values[], direction, rate_per_session}
anomaly_flags:         [{name, confidence, description, severity}]
fsm_references:        [{section, page, description}]   # from RAG
user_query:            str
session_count:         int
fleet_pattern_match:   None  # Tier 5, not implemented
lstm_reconstruction:   None  # Tier 4, not implemented
previous_reports_summary: str | None
extra_context:         dict
```

---

## 8. Database Schema

**Engine:** PostgreSQL 16 | **Init:** `scripts/init_db.sql` (auto-applied by Docker on first start)
**Migration:** `scripts/migrate_add_user_llm_configs.sql` (must be applied manually after init)

### Tables

```sql
vehicles
  id UUID PK, vehicle_id TEXT UNIQUE, make, model, year, engine TEXT,
  vin_hash TEXT (SHA-256 only), created_at, updated_at TIMESTAMPTZ

sessions
  id UUID PK, vehicle_id FK → vehicles.vehicle_id,
  filename TEXT UNIQUE, session_date DATE, session_time TIME,
  duration_min, sample_count, avg_rpm, max_rpm, avg_speed_kmh, max_speed_kmh,
  avg_coolant_c, max_coolant_c, avg_engine_load, ltft_b1, stft_b1,
  avg_timing, avg_maf, pct_time_moving, fuel_level_pct, battery_v,
  health_score INTEGER, created_at TIMESTAMPTZ

anomaly_results
  id UUID PK, session_id FK → sessions.id,
  method TEXT, anomaly_score NUMERIC, is_anomaly BOOLEAN,
  flagged_pids TEXT[], details JSONB, created_at TIMESTAMPTZ

maintenance_predictions
  id UUID PK, session_id FK → sessions.id, vehicle_id TEXT,
  target TEXT, label TEXT, health_score NUMERIC, stress_score NUMERIC,
  severity TEXT (normal|warning|critical), confidence NUMERIC,
  contributing_pids TEXT[], recommendation TEXT, created_at TIMESTAMPTZ

diagnostic_reports
  id UUID PK, session_id FK → sessions.id, vehicle_id TEXT,
  dtc_codes TEXT[], anomaly_count INTEGER, rag_query TEXT,
  rag_grounded BOOLEAN, report_text TEXT, model_used TEXT, created_at TIMESTAMPTZ

alerts
  id UUID PK, session_id FK → sessions.id, vehicle_id TEXT,
  pid, label, severity, value NUMERIC, unit, message TEXT, created_at TIMESTAMPTZ

ollama_analyses
  id UUID PK, session_filename TEXT, question TEXT, model TEXT,
  response_text TEXT, alerts TEXT[], sample_count INT, duration_min NUMERIC,
  created_at TIMESTAMPTZ

app_user_accounts
  id UUID PK, email TEXT UNIQUE, username, display_name, pw_hash TEXT,
  account_json JSONB, created_at, updated_at TIMESTAMPTZ

users  ← from migration
  id UUID PK, supabase_uid TEXT UNIQUE, vehicle_id FK,
  email_hint VARCHAR(8), created_at, updated_at TIMESTAMPTZ

user_llm_configs  ← from migration
  id UUID PK, user_id FK → users.id,
  provider VARCHAR(32), model_id VARCHAR(128),
  encrypted_api_key BYTEA, key_iv BYTEA, key_hint VARCHAR(8),
  is_active BOOLEAN, created_at, updated_at, last_used_at TIMESTAMPTZ
  UNIQUE(user_id, provider)
```

**⚠️ Note:** `sessions.vehicle_id` is a `TEXT` FK to `vehicles.vehicle_id` (the pseudonymous ZK token), not the UUID `id`. This is intentional for privacy.

---

## 9. Frontend (React Web App)

**Stack:** Vite + React 18 + TypeScript + Tailwind CSS
**Deployed:** Cloudflare Pages → `cactus-app.io` (auto-deploy on push to `main`)
**Dev:** `npm run dev` at `frontend/`

### Pages & Routes

| Page | File | What it does |
|---|---|---|
| Landing | `Landing.js` | Marketing page, hero + features |
| Auth | `Auth.js` | Login / register (hits `/api/v1/auth/*`) |
| Dashboard | `Dashboard.js` | Health ring, anomaly cards, session list, sparklines |
| Insights | `Insights.js` | SSE streaming of LLM insight tokens |
| NeedleNest | `NeedleNest.js` | Gauge visualization (coolant, RPM, fuel trim, battery) |
| Sessions | `Sessions.js` | Session list + detail view |
| Vehicles | `Vehicles.js` | Vehicle registry |
| Settings | `Settings.js` | User settings + BYOK key management UI |
| About | `About.js` | About page |

**API base (`frontend/src/config.js`):**
- Production: `https://api.acty-labs.com`
- Dev (when `NODE_ENV !== production`): `http://192.168.68.138:8765`

**Auth:** Supabase client (`supabaseClient.js`) + custom account bridge (`authApi.js`).

---

## 10. Android App

**Stack:** Kotlin + Jetpack Compose + Material 3
**Target:** Android 8.0+ (API 26+)
**Bluetooth:** Classic SPP/RFCOMM (Channel 1) — not BLE for OBD capture

### Key Classes

| Class | File | Purpose |
|---|---|---|
| `ObdCaptureService` | `bluetooth/ObdCaptureService.kt` | Foreground service, BT connection, PID polling, CSV write |
| `ELM327` | `bluetooth/ELM327.kt` | RFCOMM socket, AT command layer, hex decode |
| `PidRegistry` | `bluetooth/PidRegistry.kt` | All PID decoders (150+ functions) |
| `SyncManager` | `sync/SyncManager.kt` | WiFi-gated CSV upload, base64 encode, `.sync_manifest` dedup |
| `SessionSigner` | `crypto/SessionSigner.kt` | Ed25519 signature on CSV |
| `AuthManager` | `data/AuthManager.kt` | Login/register/account sync |
| `CsvWriter` | `data/CsvWriter.kt` | CSV file writer |
| `ActyPrefs` | `data/ActyPrefs.kt` | SharedPreferences wrapper |

### ELM327 init sequence
`ATZ` → `ATE0` → `ATL0` → `ATS0` → `ATH0` → `ATSP0` → `ATAT1`

### Screens (Jetpack Compose)
`Home`, `Capture` (live RPM chart + fuel trim), `Sessions`, `Insights` (SSE), `OBDDevices` (pairing), `Account`, `Login`, `Register`, `NeedleNest`, `LLMSettings` (BYOK), `Sharing`, `About`

### Known issues
- **Bluetooth pairing not fully stable** — RFCOMM socket binding intermittent
- **Data sync not reaching web app** — Supabase JWT not shared correctly between Android and web; auth session mapping broken. Sessions uploaded by Android are not visible in `cactus-app.io`

---

## 11. iOS App

**Status: ⛔ NOT FUNCTIONAL — placeholder only**

Only 3 stub files exist: `ActyApp.swift`, `ContentView.swift`, `CaptureViewModel.swift`.
No Bluetooth, no OBD, no API integration. Development not started.

**Hard constraint:** iOS must use BLE only (not Classic Bluetooth SPP). The VeePeak OBDCheck BLE supports both; iOS must use BLE mode.

---

## 12. MCP Server

**File:** `mcp/acty_mcp_server.py`
**Port:** 8767 (SSE transport)
**Config:** `mcp/.env.mcp` (gitignored, must be created on 4U server)
**Claude Code wiring:** `.mcp.json` → `http://192.168.68.138:8767/sse`
**Service:** `mcp/acty-mcp.service` (systemd, auto-start)
**Deploy:** `mcp/deploy.sh`

### Tools exposed to Claude

| Tool | DB/API | Purpose |
|---|---|---|
| `list_sessions(vehicle_id, limit)` | DB | Recent sessions for a vehicle |
| `list_vehicles()` | DB | All registered vehicles |
| `get_session_summary(session_id)` | DB | Full diagnostic summary (LTFT, voltage, timing, thermal, engine) |
| `get_session_pids(session_id, pids)` | DB | Raw time-series for specific PIDs |
| `get_vehicle_history(vehicle_id, sessions)` | DB | Cross-session LTFT/voltage/timing trend |
| `get_dtc_history(vehicle_id)` | DB | All DTC events across sessions |
| `query_fsm_rag(question, vehicle)` | RAG server | FSM manual lookup via NL question |
| `generate_report(session_id, model)` | API | Trigger Ollama report via acty-api |
| `run_anomaly_check(session_id)` | API | Isolation Forest pass via acty-api |
| `ask_ollama(prompt, model)` | Ollama | Raw prompt to local Ollama |
| `list_ollama_models()` | Ollama | List available models |
| `verify_session(session_id)` | verify.acty-labs.com | 7-layer session integrity check |
| `get_session_manifest(session_id)` | DB | Signed manifest (Merkle root, Ed25519, TSA) |
| `list_csv_archive(vehicle_id)` | TrueNAS | List raw CSVs on share1 |
| `read_csv_head(relative_path, rows)` | TrueNAS | Preview CSV from archive |
| `platform_health()` | All services | Health check: DB, API, RAG, Ollama, Grafana, TrueNAS |

---

## 13. OBD Capture Script (Python)

**File:** `acty_obd_capture.py` (Linux Mint / Pi 3B)
**Target adapter:** VeePeak OBDCheck BLE, MAC `8C:DE:52:D9:7E:D1`, Classic BT SPP

**PID set (default, no probe):**
`RPM, SPEED, COOLANT_TEMP, ENGINE_LOAD, THROTTLE_POS, INTAKE_TEMP, MAF, SHORT_FUEL_TRIM_1, LONG_FUEL_TRIM_1, TIMING_ADVANCE, INTAKE_MAP, FUEL_LEVEL`

**Auto-probe mode** queries vehicle for all supported PIDs (Mode 01 supported PIDs bitmask), builds dynamic list.

**Output:** `acty_obd_YYYYMMDD_HHMMSS.csv` with `timestamp, elapsed_s, [PID columns...]`

---

## 14. Test Fleet

| Vehicle | Engine | Known Issues |
|---|---|---|
| 2023 GR86 (primary) | FA24 2.4L D-4ST | **Persistent lean LTFT -6.5% to -8.2%** — 9+ sessions, never in ±5% range. Drifts lean as engine warms. Likely MAF thermal calibration drift. Action: MAF cleaning → smoke test. GR catback exhaust installed. |
| 2022 RAV4 | 2.5L M20A-FKS D-4ST | LTFT excellent (STFT +0.16%, LTFT -0.74%). PM sensor B1 present. Auto start-stop disabled (was interrupting OBD logging). |
| 2006 Tacoma | 2TR-FE 2.7L | **Alternator failing thermally** — avg 12.87V, never reaches 13.5V. LTFT reset after battery replacement. OBD readiness monitors incomplete (would fail TX inspection). |

**Diagnostic thresholds:**
- STFT/LTFT: normal ±5%, warning ±7.5%, action ±10%
- Battery voltage (running): normal 13.8–14.5V, concern <13.5V sustained, critical <13.0V
- Coolant warmup: normal <5 min to 80°C, suspect thermostat if >8 min

---

## 15. Cryptographic Architecture

**Ed25519 signing:**
- Private key in ATECC608B hardware secure element on CM3588 (never exported)
- Each session: signed manifest `{session_id, merkle_root, timestamp, signature}`
- Public key at `/.well-known/acty-signing-key.pub`

**Hash-chain per OBD record:**
```python
{
  "seq": int,
  "timestamp": ISO8601,
  "pids": { ... },
  "prev_hash": sha256_hex,      # hash of previous record
  "record_hash": sha256_hex     # sha256(seq + timestamp + pids + prev_hash)
}
```

**Session manifest:**
```python
{
  "session_id": uuid,
  "vehicle_id": uuid,
  "record_count": int,
  "merkle_root": sha256_hex,
  "rfc3161_timestamp": bytes,   # DigiCert TSA anchor
  "ed25519_signature": hex,
  "firmware_hash": sha256_hex
}
```

**BYOK encryption:** AES-256-GCM, server-side master key (`CACTUS_KEY_ENCRYPTION_KEY`). Pre-TEE phase only — plaintext keys must not leave API process. Future: AMD SEV-SNP TEE on Dell R7525 (blocked — PSP fault).

---

## 16. What Actually Works End-to-End

### ✅ Confirmed functional
- Bluetooth OBD capture (Android app + Python script)
- CSV writing and local storage
- Session upload via WiFi (Android SyncManager)
- PostgreSQL persistence of sessions + anomaly results
- API health checks
- Session summary computation (stats aggregation)
- Isolation Forest anomaly detection
- SSE streaming (insights + Ollama analyze)
- BYOK key encryption and storage (7 providers wired)
- Local Ollama fallback (deepseek-r1:14b)
- RAG retrieval from FSM (when server up)
- React web dashboard (health ring, sparklines, anomaly cards)
- Supabase JWT validation (when secret set)
- Account sync between web and Android (account_json bridge)
- MCP server SSE transport + tool access to DB/API

### ⚠️ Partially working
- **Multi-provider BYOK LLM** — encryption works, validation disabled (TODO)
- **Predictive maintenance** — Isolation Forest connected; XGBoost/RF architecture defined but training pipeline not fully traced
- **LSTM anomaly detection** — architecture described, not implemented
- **Data sync web ↔ Android** — account sync works; session data not consistently visible cross-platform

### ⛔ Not implemented / broken
- **iOS app** — stub only, no functionality
- **Supabase session sharing** — Android sessions not reliably visible in web app
- **Fleet learning (Tier 5)** — placeholder
- **Job store persistence** — in-memory only, lost on restart (needs Redis)
- **TEE integration** — future (blocked by R7525 PSP fault)
- **Password security** — prototype-only (no bcrypt, no salt)
- **BYOK key validation** — registration accepts keys without verifying them

---

## 17. Active Known Issues

### 🔴 Android Bluetooth pairing
Intermittent RFCOMM socket binding failures with VeePeak OBDCheck BLE. Expected: discover → pair → RFCOMM channel 1 → ELM327 handshake → PID stream. Check: `BLUETOOTH_CONNECT`, `BLUETOOTH_SCAN` permissions (Android 12+), foreground service lifecycle, ELM327 init sequence timing.

### 🔴 Data not persisting web ↔ Android
User logs session in Android → not visible in `cactus-app.io`.
Root cause: Supabase JWT not consistently threaded between Android and API; or `users.supabase_uid` not mapping to `vehicles.vehicle_id` correctly. Android uploads to `/api/v1/sessions/sync` but sessions table `vehicle_id` may not match what the web queries.

### 🟡 In-memory job store
`insights.py` uses `asyncio.Queue` per `job_id` (module-level dict). Fine for single-instance dev. Production needs Redis pub/sub.

### 🟡 Password storage
`auth.py` `POST /register` stores `pw_hash` as a plain string with no bcrypt. `POST /login` compares with `==`. This is the prototype bridge — must be replaced before production user growth.

### 🟡 BYOK key validation disabled
`llm_config.py` `POST /{provider}/validate` skips actual validation. Users can store invalid keys.

---

## 18. Deployment Checklist Status (from DEPLOYMENT_CHECKLIST.md)

| Item | Status | Notes |
|---|---|---|
| Migrations applied | ⚠️ Partial | `init_db.sql` auto-runs in Docker. `migrate_add_user_llm_configs.sql` must be applied manually. No Alembic — raw SQL only. |
| DB initialized | ✅ | Docker auto-applies via `docker-entrypoint-initdb.d/init.sql` |
| Backups configured | ❌ | No backup script exists yet |
| Least-privilege DB user | ❌ | `docker-compose.yml` runs `POSTGRES_USER: acty` (superuser) for app connections |
| Connection pooling | ❌ | `get_db_connection()` creates a new `asyncpg.connect()` per request — no pool |
| Production connection string | ⚠️ | `DATABASE_URL=postgresql://acty:acty@postgres:5432/acty-postgres` — password `acty` is not production-safe |

---

## 19. Environment Variables Reference

**Required for backend:**
```env
DATABASE_URL          # postgresql://user:pass@host:5432/db
OLLAMA_HOST           # http://192.168.68.138:11434
RAG_BASE_URL          # http://192.168.68.138:8766
CACTUS_KEY_ENCRYPTION_KEY  # 32-byte base64 for BYOK AES-256-GCM
SUPABASE_JWT_SECRET   # from Supabase → Settings → API → JWT Settings
```

**Required for MCP server (`mcp/.env.mcp`):**
```env
ACTY_DB_DSN           # postgresql://acty:...@localhost:5432/acty-postgres
ACTY_API_BASE         # http://192.168.68.138:8765
ACTY_RAG_BASE         # http://192.168.68.138:8766
ACTY_OLLAMA_BASE      # http://192.168.68.138:11434
MCP_TRANSPORT=sse
MCP_PORT=8767
```

**Frontend:**
```env
REACT_APP_SUPABASE_URL     # https://xxxx.supabase.co
REACT_APP_SUPABASE_ANON_KEY  # public anon key only
REACT_APP_API_URL          # https://api.acty-labs.com (production)
```

---

## 20. Repository Structure

```
acty-project/
├── backend/
│   ├── api/
│   │   ├── server.py          # FastAPI entry point, core endpoints
│   │   ├── deps.py            # Supabase JWT dependency
│   │   └── routers/
│   │       ├── auth.py        # Account bridge
│   │       ├── insights.py    # BYOK LLM + SSE streaming
│   │       ├── llm_config.py  # BYOK key management
│   │       ├── ollama_router.py  # Ollama direct access
│   │       └── sessions_router.py  # Android sync
│   ├── llm/
│   │   ├── providers.py       # Abstract base + registry
│   │   ├── key_encryption.py  # AES-256-GCM for BYOK keys
│   │   ├── anthropic.py, openai_provider.py, google.py,
│   │   │   cohere.py, mistral.py, groq_provider.py,
│   │   │   deepseek.py, fallback.py
│   └── ml/
│       ├── pipeline/          # ML stages (anomaly, predictive, reports)
│       └── rag/server/        # ChromaDB + Ollama RAG server
├── frontend/src/              # React 18 pages + API calls
├── acty-android/              # Kotlin + Jetpack Compose Android app
├── acty-ios/                  # ⛔ Stub only — 3 files
├── mcp/
│   ├── acty_mcp_server.py    # FastMCP SSE server, 15 tools
│   ├── acty-mcp.service      # systemd unit
│   ├── deploy.sh             # One-shot 4U server setup
│   └── requirements-mcp.txt
├── hardware/
│   └── acty_obd_capture.py   # Python OBD capture script
├── scripts/
│   ├── init_db.sql            # Full schema (auto-applied by Docker)
│   └── migrate_add_user_llm_configs.sql  # Must apply manually
├── docker-compose.yml         # Dev stack (api, postgres, grafana)
├── docker-compose.prod.yml    # Production stack
├── Caddyfile                  # Caddy reverse proxy config (CM3588)
├── .mcp.json                  # Claude Code MCP server wiring
└── .env                       # Dev secrets (gitignored)
```

---

*Document reflects codebase as of April 2026. Generated from live code audit — not from documentation alone.*
