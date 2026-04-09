# Acty / Cactus — Codebase Summary

> Read this first. One scroll = full picture of where everything lives and what it does.

---

## What This Is

**Acty** is a privacy-first OBD-II vehicle diagnostics platform. A Bluetooth dongle plugs into your car's OBD port. The Android app reads sensor data (PIDs), signs it cryptographically, and uploads it to the backend. The backend runs anomaly detection, RAG-grounded AI diagnostics, and streams insights back to the user — using their own LLM API key (BYOK).

**Core promise:** Owner-encrypted data. Tamper-evident signed reports. AI diagnostics without selling user data.

---

## Repo Layout

```
acty-project/
├── backend/
│   ├── api/
│   │   ├── server.py              ← FastAPI app (main entry point)
│   │   └── routers/
│   │       ├── insights.py        ← LLM insight generation (SSE streaming)
│   │       └── llm_config.py      ← BYOK key registration & management
│   ├── llm/
│   │   ├── providers.py           ← Provider registry + CactusPrompt contract
│   │   ├── key_encryption.py      ← AES-256-GCM key wrapping
│   │   ├── prompt_builder.py      ← Build structured prompts from pipeline output
│   │   ├── anthropic.py           ← Claude provider
│   │   ├── openai_provider.py     ← GPT-4o, o3, o4-mini provider
│   │   ├── google.py              ← Gemini provider
│   │   ├── cohere.py              ← Cohere provider
│   │   ├── mistral.py             ← Mistral provider
│   │   ├── groq.py                ← Groq/Llama provider
│   │   ├── deepseek.py            ← DeepSeek provider (OpenAI SDK, custom base_url)
│   │   └── fallback.py            ← Local Ollama (no API key needed)
│   ├── ml/
│   │   ├── pipeline/
│   │   │   ├── anomaly.py         ← Isolation Forest anomaly detection
│   │   │   ├── predictive.py      ← XGBoost failure prediction
│   │   │   ├── battery_health.py  ← Battery/alternator health monitor
│   │   │   ├── oil_change_detector.py ← Detect oil changes from PID patterns
│   │   │   ├── maintenance_tracker.py ← Cross-session maintenance history
│   │   │   ├── oil_interval_advisor.py← Oil change interval predictor
│   │   │   ├── oil_level_estimator.py ← Oil level estimate (no sensor)
│   │   │   ├── obd_normalize.py   ← Normalize raw OBD CSV data
│   │   │   └── report.py          ← RAG-grounded diagnostic report builder
│   │   └── rag/
│   │       ├── 01_parse_fsm.py    ← Parse service manual PDFs into chunks
│   │       ├── 02_embed.py        ← Embed chunks into ChromaDB
│   │       ├── 03_query.py        ← Semantic search
│   │       └── server/
│   │           ├── rag_server.py  ← FastAPI RAG server (port 8766)
│   │           ├── retriever.py   ← ChromaDB query logic
│   │           └── ingest.py      ← Upload/process service manuals
│   └── tests/
│       └── test_byok.py           ← BYOK pytest suite (10 test classes)
├── hardware/
│   └── acty_obd_capture.py        ← CANONICAL Linux OBD capture script
├── acty-android/app/src/main/java/com/acty/
│   ├── bluetooth/
│   │   ├── ObdCaptureService.kt   ← Foreground service (BT session lifecycle)
│   │   ├── ELM327.kt              ← AT command protocol over RFCOMM
│   │   └── PidRegistry.kt         ← OBD-II PID definitions (70+ PIDs)
│   ├── data/
│   │   ├── CsvWriter.kt           ← CSV rows + Merkle-tree hash chain
│   │   ├── SessionSigner.kt       ← Ed25519/EC signing via Android Keystore
│   │   └── SyncManager.kt         ← WiFi upload to acty-api (OkHttp)
│   ├── model/
│   │   ├── SessionState.kt        ← Data class: isRunning, pidValues, DTCs
│   │   └── SessionEvent.kt        ← Sealed class: Started/Stopped/Error/SyncProgress
│   └── ui/
│       ├── MainActivity.kt        ← Fragment container, FAB start/stop
│       ├── SessionViewModel.kt    ← Service binding, state flow
│       ├── LiveSessionFragment.kt ← Real-time PID display + RPM chart
│       ├── SessionsFragment.kt    ← Previous sessions list
│       └── settings/
│           └── LLMSettingsScreen.kt ← BYOK provider key registration UI
├── scripts/
│   ├── init_db.sql                ← Core schema (6 tables)
│   └── migrate_add_user_llm_configs.sql ← BYOK tables (users, user_llm_configs)
├── data_capture/                  ← OBD CSV files (local, not committed)
├── capture_sync.py                ← Sync CSVs to TrueNAS SMB share
├── docker-compose.yml             ← api + postgres + grafana + pgadmin
├── requirements.txt               ← Python deps (backend + ML + LLM SDKs)
└── CACTUS_CODE_BEST_PRACTICES.md  ← Architecture rules (read before touching anything)
```

---

## How Data Flows

```
[Car OBD Port]
     ↓  Bluetooth RFCOMM SPP
[Android App]
  ELM327.kt sends AT commands, reads PID bytes
  PidRegistry.kt decodes raw bytes → named values (RPM, COOLANT_TEMP, etc.)
  CsvWriter.kt writes timestamped rows + SHA-256 hash chain
  SessionSigner.kt signs Merkle root with Ed25519 (Android Keystore)
  SyncManager.kt POSTs CSV + .sig to backend on WiFi
     ↓  HTTP multipart/form-data
[Backend — server.py POST /upload]
  Validates CSV, stores to PostgreSQL (sessions, session_rows tables)
  detect_anomalies(df) → Isolation Forest + rule thresholds → alerts table
  Saves session summary stats → sessions table
     ↓  user taps "Get AI Insight"
[Backend — insights.py POST /api/v1/insights/generate]
  Returns 202 Accepted + job_id immediately (never blocks)
  Background task: _build_cactus_prompt() pulls from DB + RAG server
  Streams LLM tokens into asyncio.Queue
     ↓  SSE stream
[Backend — insights.py GET /api/v1/insights/stream/{job_id}]
  Reads tokens from queue, emits as text/event-stream
     ↓  Android app renders tokens as they arrive
```

---

## Key Files — What They Do

### `backend/api/server.py`
The FastAPI application. Handles CSV uploads, runs Tier 1 anomaly detection, builds session summaries.

| Function | Does |
|---|---|
| `lifespan(app)` | Startup: validates CACTUS_KEY_ENCRYPTION_KEY, opens asyncpg pool |
| `detect_anomalies(df)` | Rule thresholds + Isolation Forest → list of alerts with severity |
| `summarize_session(df, path)` | Stats dict: avg RPM, max speed, LTFT, coolant warm-up time, etc. |
| `_generate_insights(df, stats)` | Rule-based insight cards (no LLM) — fast Tier 1 output |
| `POST /upload` | Accept CSV, validate, store, run pipeline, return anomaly list |

Add new ingest logic here. Add new insight rules in `_generate_insights()`.

---

### `backend/api/routers/insights.py`
Non-blocking LLM insight generation via SSE.

| Function | Does |
|---|---|
| `generate_insight()` | POST → 202 immediately, spawns background LLM task, returns job_id |
| `stream_insight()` | GET → SSE, reads tokens from asyncio.Queue, streams to client |
| `_build_cactus_prompt()` | Pulls vehicle/session/anomaly/LTFT data from DB, calls RAG server, assembles CactusPrompt |
| `_run_llm_generation()` | Background task: calls provider.stream_insight(), puts tokens in Queue |

**Important:** Module-level `_job_store: dict[str, Queue]` is in-memory. Must run `--workers 1` until Redis pub/sub is implemented.

---

### `backend/api/routers/llm_config.py`
BYOK provider key CRUD.

| Function | Does |
|---|---|
| `register_key()` | Validate key with provider, encrypt with AES-GCM, upsert to DB |
| `list_configs()` | Return all user's providers — key_hint only, never plaintext |
| `delete_config()` | Remove provider config |
| `validate_key_endpoint()` | Test a key without saving (form validation) |
| `fetch_decrypted_key()` | Internal helper: decrypt key from DB for use in insight generation |

---

### `backend/llm/providers.py`
Registry and contract layer.

| Component | Does |
|---|---|
| `CactusPrompt` | Structured dataclass passed to every LLM. Contains pre-analyzed features only — **never raw PID values**. |
| `LLMProvider` | ABC: `stream_insight()` → AsyncGenerator[str], `validate_key()` → bool |
| `get_provider(id)` | Look up provider by string ID (e.g., "anthropic") |
| `get_fallback_provider()` | Returns local Ollama provider — used when user has no BYOK key |
| `list_providers()` | Returns all providers with supported models + cost estimates |

Add a new provider: create a file in `backend/llm/`, subclass `LLMProvider`, add to `_build_registry()`.

---

### `backend/llm/key_encryption.py`
AES-256-GCM key wrapping. The only place plaintext API keys touch Python memory.

| Function | Does |
|---|---|
| `encrypt_api_key(key)` | Returns (ciphertext: bytes, nonce: bytes). Nonce is random 12 bytes. |
| `decrypt_api_key(ciphertext, nonce)` | Returns plaintext str. Raises InvalidTag if tampered. |
| `make_key_hint(key)` | Returns `"...XXXX"` (last 4 chars). Safe to store/display. |
| `_load_master_key()` | Reads CACTUS_KEY_ENCRYPTION_KEY env var, validates 32-byte length. |

---

### `backend/llm/prompt_builder.py`
Assembles structured prompts from pipeline tier output. Controls what the LLM sees.

| Function | Does |
|---|---|
| `build_prompt(...)` | Combines vehicle context, LTFT trend, anomaly flags, FSM refs, previous reports |
| `render_prompt_messages(prompt)` | Returns `[{role: system, ...}, {role: user, ...}]` for provider SDKs |
| `_session_tier(count)` | "session_1" / "early" (2-4) / "mature" (5+) — controls how much longitudinal analysis to request |
| `_system_prompt(tier, has_fleet)` | Tier-aware system prompt (FSM emphasis early, full longitudinal when mature) |

---

### `backend/ml/pipeline/anomaly.py`
Tier 1 CPU anomaly detection.

| Function | Does |
|---|---|
| `run_isolation_forest(df)` | Fits Isolation Forest on 11 PIDs. Returns `AnomalyResult` with score, is_anomaly flag, flagged PIDs. Requires 50+ samples. |

---

### `backend/ml/rag/server/rag_server.py`
RAG retrieval FastAPI server (port 8766). Separate process from main API.

| Endpoint | Does |
|---|---|
| `POST /retrieve` | Semantic search ChromaDB → top-k chunks from service manual |
| `POST /context` | Return formatted context string from retrieved chunks |
| `POST /query` | Full RAG: retrieve + call Ollama + return answer with sources |

Ingest new service manuals via `01_parse_fsm.py` → `02_embed.py`.

---

### `scripts/init_db.sql`
Core PostgreSQL schema. **Run once on fresh DB.**

| Table | Stores |
|---|---|
| `vehicles` | vehicle_id (pseudonymous), make, model, year, vin_hash (SHA-256 only) |
| `sessions` | Per-session stats (duration, avg RPM, LTFT, health_score, filename) |
| `session_rows` | **Append-only.** Every OBD row. Never UPDATE or DELETE. |
| `anomaly_results` | Isolation Forest + LSTM outputs per session |
| `maintenance_predictions` | XGBoost health/stress scores per system |
| `diagnostic_reports` | RAG-grounded LLM report text per session |
| `alerts` | Per-PID threshold violations with severity |

`migrate_add_user_llm_configs.sql` adds `users` and `user_llm_configs` tables (run after init_db).

---

### `hardware/acty_obd_capture.py`
**The canonical Linux OBD capture script.** Run on Linux Mint dev machine.

| Component | Does |
|---|---|
| `PID_REGISTRY` | Dict of 70+ PIDs: name → (mode_pid_hex, description, unit, decoder_fn) |
| `ELM327` class | Sends AT commands over RFCOMM socket, parses hex responses |
| `ELM327.probe_supported_pids()` | Queries Mode 01 bitmasks → set of supported PIDs for this vehicle |
| `ELM327.get_dtcs()` / `get_pending_dtcs()` | Mode 03 / Mode 07 DTC reads |
| `DataLogger` class | Writes CSV with `timestamp, elapsed_s, [PIDs], DTC_CONFIRMED, DTC_PENDING` |
| `main()` | CLI: connect BT → probe → poll loop → periodic DTC refresh → graceful SIGINT |

```bash
# Typical usage
python3 hardware/acty_obd_capture.py                    # probe + poll all supported PIDs
python3 hardware/acty_obd_capture.py --no-probe         # use default 12 PIDs
python3 hardware/acty_obd_capture.py --dtc              # read DTCs and exit
python3 hardware/acty_obd_capture.py --dtc-interval 60  # refresh DTCs every 60 cycles
```

Output lands in `~/acty-project/data_capture/`. `capture_sync.py` picks it up from there.

---

### `capture_sync.py`
Syncs CSV files from `~/acty-project/data_capture/` to TrueNAS SMB share when on home LAN.

```bash
python3 capture_sync.py            # sync new files
python3 capture_sync.py --dry-run  # preview without copying
python3 capture_sync.py --status   # show what's pending
```

Uses a `.sync_manifest` file to avoid re-uploading. Requires `ACTY_SMB_PASSWORD` env var or prompts.

---

### Android — `ObdCaptureService.kt`
Android foreground service. The Bluetooth session lifecycle lives here.

| Component | Does |
|---|---|
| `startCapture()` | Opens RFCOMM socket to dongle, init ELM327, probe PIDs, start poll loop |
| Poll loop | Every 1s: query each PID → decode → emit to `state: StateFlow<SessionState>` |
| DTC refresh | Every 30 cycles: reread Mode 03/07, alert if codes change |
| `stopCapture()` | Close socket, flush CSV, compute Merkle root, sign session, trigger SyncManager |

UI binds to this service. `SessionViewModel.kt` bridges service state to Compose/Fragment UI.

---

### Android — `CsvWriter.kt` + `SessionSigner.kt`
| Component | Does |
|---|---|
| `CsvWriter.writeRow()` | Appends CSV row + SHA-256(prev_row) hash chain link |
| `CsvWriter.getMerkleRoot()` | Builds Merkle tree from all row hashes → single root hash |
| `SessionSigner.signSession()` | Signs Merkle root + session metadata with Ed25519 (Android Keystore) → `.sig` JSON |

This is what makes the data tamper-evident. Backend can re-verify hash chain + signature independently.

---

## Database Connection

`server.py` holds a module-level `_pool: asyncpg.Pool | None`. Routers access it via:
```python
from api import server as _server
pool = _server._pool  # deferred import at request time
```

Never scan `sys.modules` for the pool — use the direct import above.

---

## Environment Variables (Required)

| Var | Used by | Purpose |
|---|---|---|
| `CACTUS_KEY_ENCRYPTION_KEY` | `key_encryption.py` | Base64-encoded 32-byte master key for AES-256-GCM |
| `DATABASE_URL` | `server.py` | asyncpg connection string |
| `CACTUS_RAG_URL` | `insights.py` | RAG server URL (default: `http://localhost:8766`) |
| `CACTUS_LOCAL_INFERENCE_URL` | `fallback.py` | Ollama URL (default: `http://localhost:11434`) |
| `CACTUS_LOCAL_MODEL` | `fallback.py` | Local model name (default: `deepseek-r1:14b`) |
| `DEEPSEEK_API_BASE` | `deepseek.py` | DeepSeek API base URL (default: `https://api.deepseek.com`) |

---

## Where To Add or Fix Things

| Task | Where |
|---|---|
| New anomaly rule | `backend/api/server.py` → `detect_anomalies()` or `_generate_insights()` |
| New LLM provider | Create `backend/llm/yourprovider.py`, subclass `LLMProvider`, add to `providers.py._build_registry()` |
| New API endpoint | `backend/api/routers/` — new file or add to existing router |
| New PID | Add to `PID_REGISTRY` in `hardware/acty_obd_capture.py` AND `acty-android/.../PidRegistry.kt` |
| New DB table | Add to `scripts/init_db.sql` + write a migration SQL file |
| New service manual (RAG) | Run `ml/rag/01_parse_fsm.py` then `02_embed.py` on the PDF |
| New UI screen (Android) | Add Composable in `acty-android/.../ui/`, add to navigation in `MainActivity.kt` |
| Session summary stat | Add to `summarize_session()` in `server.py` + add column to `sessions` table |

---

## Non-Negotiable Rules

1. **Never pass raw PID values to LLM.** Always use `CactusPrompt` with pre-analyzed features.
2. **`session_rows` is append-only.** No UPDATE, no DELETE, ever.
3. **No real user data in dev.** Only synthetic sessions in dev/staging PostgreSQL.
4. **Key plaintext never leaves `key_encryption.py`.** Don't log it, don't return it, don't store it.
5. **SSE for all LLM streaming.** Never block a request waiting for LLM output.
6. **Stateless FastAPI.** No in-memory request state except the current dev `_job_store` (which needs Redis before multi-worker deploy).
7. **Config in env vars only.** No hardcoded ports, keys, or model names.
