# Cactus / Acty Project — Claude Code Context File
> Last updated: April 2026  
> For use with Claude Code as primary project context. Load this file at the start of every session.

---

## What Acty/Cactus Is

Acty is a privacy-first OBD-II vehicle telemetry and diagnostics platform. The flagship product is **Cactus** (Continuous Automotive Condition & Telemetry Unified System).

**Core value proposition:** Owner-encrypted data, tamper-evident signed reports, and ML-powered insights — without selling user data.  
**Revenue model:** Hardware sales + verified `.acty` report fees. No data brokerage. No VC funding.  
**GitHub:** `JacobChamblee/acty-project` (main), `JacobChamblee/acty-fsm-rag` (FSM RAG pipeline)  
**Domain:** acty-labs.com (Namecheap, DNS on Cloudflare)  
**Stage:** Active development / beta prep

---

## Architecture Overview

```
[OBD-II Dongle] → [Capture Device] → [Ingest Server] → [ML Pipeline] → [Reports]
     VeePeak           Android app        FastAPI           Ollama/vLLM     Ed25519
   OBDCheck BLE      Kotlin/Compose      PostgreSQL         RAG/LLM          signed
  MAC: 8C:DE:52:D9:7E:D1  BT SPP        Grafana          ChromaDB        .acty file
```

### Six-Stage ML Pipeline
1. Isolation Forest (anomaly detection) — CPU, synchronous
2. LSTM Autoencoder / TFT — GPU, async background
3. XGBoost / Random Forest (predictive maintenance) — CPU, synchronous
4. RAG (FSM-grounded AI diagnostics) — GPU embedding + LLM
5. Federated Learning (Flower framework, ε ≤ 1.0 differential privacy) — nightly batch
6. Ed25519 report signing (ATECC608B hardware secure element or YubiHSM server-side)

### Tiered Insight Pipeline (Request Flow)
```
User Request → [Tier 0: Redis Cache] → hit: return immediately
                      ↓ miss
             [Tier 1: CPU Ensemble] → Isolation Forest + XGBoost < 2s
                      ↓ anomaly found
             [Tier 2: RAG Retrieval] → ChromaDB + BAAI embeddings 2–8s
                      ↓
             [Tier 3: LLM Synthesis] → vLLM deepseek-r1:70B, SSE streaming
                      ↓ async
             [Tier 4: LSTM/TFT] → Celery job, GPU training lane, minutes
                      ↓ nightly
             [Tier 5: FL Aggregation] → Flower, DP-enforced, global model update
```

---

## Privacy Architecture (Non-Negotiable Constraints)

These are architectural invariants. Do NOT suggest implementations that violate them:

- **Owner-encrypted telemetry** — data encrypted with user's key (BYOK) before leaving device
- **Zero-knowledge identity** — rotating pseudonymous tokens; real identity never tied to sessions
- **Differential privacy** — ε ≤ 1.0, secure aggregation via Flower for fleet analytics
- **Ed25519 signing** — ATECC608B hardware secure element on device; private key never exported
- **Hash-chain records** — each record: `SHA256(seq + timestamp + pids + prev_hash)` → tampering breaks chain
- **Session manifest** — Merkle root of all record hashes, signed at session end
- **RFC 3161 timestamping** — DigiCert TSA anchor for court-admissible timestamps
- **Append-only audit log** — server-side hash-chain; upgrade target: Merkle tree with public transparency root
- **Verification endpoint** — `https://verify.acty-labs.com/verify/<session_id>` — 7-layer independent verification
- **Decryption boundary** — user session data decrypts in isolated TEE (AMD SEV-SNP) node; plaintext never reaches shared GPU pool
- **Dev data policy** — dev/staging PostgreSQL NEVER contains real user OBD data; synthetic sessions only

---

## Current Infrastructure

### Homelab Nodes

| Node | IP | Role | Key Specs |
|------|----|------|-----------|
| 4U DIY server | 192.168.68.138 | Inference + acty-api | i5-10400, RTX 3060 12GB, Ubuntu 24.04 |
| Dell R7525 | 192.168.68.x | ML training (future) | 2× EPYC 7542, ~512GB RAM, 8× L40 48GB incoming |
| Dell R6525 | 192.168.68.119 (iDRAC) | Secondary node | 2× EPYC 7262 (post-BIOS fix) |
| CM3588 | 192.168.68.121 | Reverse proxy + signing | 8-core ARM, 8GB, Xubuntu, Caddy |
| TrueNAS | 192.168.68.116 | Storage | pool: data1, dataset: share1, SMB share1 |
| ThinkPad X280 | — | Dev machine | Linux Mint, username: jacob |

### Running Services (4U server)
- `acty-api` — FastAPI, port 8765
- `rag_server` — FastAPI RAG, port 8766
- `PostgreSQL` — primary DB
- `ChromaDB` — vector store
- `Ollama` — port 11434, models: llama3.1:8b, nomic-embed-text, phi4-mini
- `Grafana` — port 3000

### Production Target Infrastructure (k3s cluster)
- **3× control plane nodes** (single-CPU 2U) — k3s HA, embedded etcd
- **Pool A — Service nodes** (3× dual-CPU 2U):
  - A1: FastAPI acty-api, Redis, Celery
  - A2: Ray head, Flower FL coordinator, ChromaDB
  - A3: TEE/SEV-SNP decrypt node, YubiHSM 2 (USB), signing service
- **Pool A — Utility nodes** (2× single-CPU 2U):
  - U1: PostgreSQL primary + replica, Grafana, Prometheus
  - U2: Caddy, Cloudflare tunnel, audit log, verify endpoint
- **Pool B — GPU node** (R7525): 8× L40 48GB
  - GPUs 0–3: vLLM inference lane (2× L40 per 70B instance)
  - GPUs 4–5: Embedding lane (bge-m3, nomic-embed-text)
  - GPUs 6–7: Training lane (LSTM/TFT, FL aggregation)
- **Dev nodes:** Jetson Nano (edge inference validation), X99 (staging k3s), 2× Pi 3B (watchdog + metrics)

---

## Technology Stack

### Backend
- **FastAPI** — primary API server
- **PostgreSQL** — primary database
- **ChromaDB** — vector store (migration target: pgVector for simplification)
- **Redis** — inference cache + Celery job queue
- **Celery** — async job queue for Tier 4/5 pipeline
- **Ollama** — dev inference (replace with vLLM in production)
- **vLLM** — production inference, continuous batching, PagedAttention
- **Ray** — ML workload orchestration (Ray Serve + Ray Train + Ray Data)
- **Flower** — federated learning framework

### Models
- **deepseek-r1:14B** — fast inference path (single L40)
- **deepseek-r1:70B** — deep inference (2× L40, 96GB VRAM)
- **BAAI/bge-m3** — embeddings (upgrade from bge-large-en-v1.5)
- **LSTM Autoencoder / TFT** — temporal anomaly detection (custom trained)
- **Isolation Forest + XGBoost/RF** — CPU ensemble, synchronous

### Mobile (Android)
- **Kotlin + Jetpack Compose** — primary app
- **Bluetooth SPP/RFCOMM** — OBD dongle connection
- OBD capture with cryptographic signing + Supabase auth

### File Format
- **Phase 1:** CSV + `.sig` Ed25519 signature file
- **Phase 2:** CBOR/COSE with `.acty` extension (tamper-evident binary)

---

## Capture Hardware

### Current OBD Dongle: VeePeak OBDCheck BLE
- MAC: `8C:DE:52:D9:7E:D1`
- Classic Bluetooth SPP, RFCOMM channel 1 (NOT BLE — iOS CoreBluetooth incompatible)
- ELM327 protocol over RFCOMM
- 123 named PIDs captured

### Capture Script: `acty_obd_capture.py`
- Python 3, `socket.AF_BLUETOOTH` / `BTPROTO_RFCOMM`
- `--probe`: auto-detects supported PIDs
- `--dtc`: reads confirmed (Mode 03) + pending (Mode 07) DTCs
- Per-record hash chain: `seq + timestamp + pids + prev_hash` → Ed25519 signed
- **DTC fix (March 2026):** `current_dtcs_confirmed` and `current_dtcs_pending` initialized before `try` block

### Future Hardware: ESP32-S3 Production Dongle
- ATECC608B secure element (Ed25519 in hardware)
- Native BLE (resolves iOS limitation)
- Deep sleep via OBD pin 16 (switched 12V) — zero drain parked

---

## Database Schema (PostgreSQL)

Six tables: `users`, `vehicles`, `sessions`, `session_rows`, `anomaly_results`, `maintenance_predictions`  
`diagnostic_reports`, `alerts`

### Planned PostgreSQL Extensions
- **pgVector** — replace/complement ChromaDB for embedding store (simplifies stack)
- **Timescale** — time-series partitioning + compression for session_rows (OBD data is time-series by nature)
- **pg_graphql** — optional GraphQL endpoint for developer API tier

---

## API Design Principles

- All internal service communication should move toward **gRPC** (5× faster than JSON for high-volume internal calls)
- FastAPI acty-api must be **fully stateless** — all session state in Redis, file state in PostgreSQL/TrueNAS
- Use **SSE (Server-Sent Events)** for streaming LLM responses — non-negotiable UX requirement
- Implement **idempotence** on all upload and report generation endpoints
- Use **202 Accepted** pattern for async insight requests — return `request_id` immediately, deliver result via webhook

---

## Event Sourcing Architecture (Ingest Layer)

OBD records are **immutable events**, not mutable state. This formalizes the existing hash-chain:

- `session_rows` table is **append-only by policy** — no UPDATE or DELETE ever
- Each record is an event: `{seq, timestamp, pids, prev_hash, signature}`
- Session manifest = Merkle root snapshot of all events in session
- ML features, anomaly flags, LTFT trends = **projections** of the event log, not stored state
- Future: CDC connector (Debezium) streams new events to ML pipeline via message queue

---

## Cache Strategy (Redis)

Four failure modes to handle explicitly:

| Failure | Cause | Fix |
|---------|-------|-----|
| Cache Stampede | Many requests on cache expiry | Mutex lock — first request regenerates, others wait |
| Cache Penetration | Request for non-existent session | Cache null with short TTL; bloom filter check |
| Cache Breakdown | Hot vehicle key expires under load | No expiry on hot keys; background refresh before expiry |
| Cache Crash | Redis down entirely | Circuit breaker in FastAPI — degrade to Tier 1 CPU only |

**Cache key pattern:** `SHA256(vehicle_id + session_manifest_root)` — never contains PII

---

## Async Delivery Pattern (Webhooks)

Do NOT use polling for insight delivery. Use webhooks:

1. User submits insight request → `202 Accepted` + `request_id` immediately
2. Tier 1 (CPU) completes → webhook fires to Android app → "Quick analysis ready"
3. Tier 3 (LLM) completes → webhook fires → "AI diagnostic ready" (SSE stream during generation)
4. Tier 4 (LSTM) completes → webhook fires → "Deep analysis ready" (arrives ~2 min later, feels like feature)
5. Each tier result updates the insight card progressively in the app UI

---

## 12-Factor App Compliance

| Factor | Status | Action Required |
|--------|--------|----------------|
| Codebase | ✅ Git | — |
| Dependencies | ✅ requirements.txt / Dockerfile | — |
| **Config** | ⚠️ Partial | Move ALL config to env vars / k8s Secrets; no key material in code |
| Backing services | ✅ | — |
| Build/Release/Run | ⚠️ | Separate build per service; tag Docker images with git SHA |
| **Processes (stateless)** | ⚠️ | acty-api must be fully stateless; no in-memory request state |
| Port binding | ✅ | — |
| **Concurrency** | ⚠️ | Multiple FastAPI replicas behind Caddy; horizontal scale from day 1 |
| **Disposability** | ⚠️ | SIGTERM handlers in every service; vLLM must drain in-flight requests |
| Dev/prod parity | ⚠️ | X99 staging must mirror prod k3s config |
| Logs | ⚠️ | Structured JSON logs → stdout → Prometheus/Loki |
| Admin processes | ✅ | — |

---

## Microservices Boundaries (Service Ownership)

Each service owns its own data — no cross-service DB access:

| Service | Owns | Does NOT touch |
|---------|------|----------------|
| acty-api | PostgreSQL (users, vehicles, sessions, session_rows) | ChromaDB directly |
| RAG service | ChromaDB | PostgreSQL |
| Cache/queue layer | Redis | PostgreSQL, ChromaDB |
| Signing service | YubiHSM / ATECC608B | All databases |
| Flower FL coordinator | FL checkpoints (NVMe) | Session data |

**Planned service split** (not urgent, architect toward):
- `ingest-service` — handles `/upload`, session validation, hash-chain verification
- `report-service` — handles `/generate-report`, LLM orchestration, signing
- `query-service` — handles `/query`, RAG retrieval, embedding

---

## Fault Tolerance Principles

Apply to every service:

1. **Replication** — PostgreSQL primary + replica; Redis cluster mode in production
2. **Redundancy** — 2× vLLM inference workers; 3-node k3s HA control plane
3. **Circuit breakers** — FastAPI → vLLM, FastAPI → ChromaDB, FastAPI → PostgreSQL; trip on failure, degrade gracefully
4. **Failover** — k3s handles node failover; Ray handles GPU worker failover
5. **Graceful degradation** — GPU lane down → serve Tier 1 CPU results only; never return 500 when partial results available
6. **Monitoring** — Prometheus node exporter on every node; alert on anomalies not just outages

---

## Key Management (Sensitive Data)

- **Device keys:** Ed25519 via ATECC608B (hardware, never exported)
- **Server countersignature:** Ed25519 via YubiHSM 2 (FIPS 140-2 Level 3, USB-attached to A3 node)
- **User data encryption:** AES-256-GCM; cipher data and keys stored separately (GCM pattern)
- **Key storage roles:** Consider Shamir's Secret Sharing for server-side key — applicant + manager + auditor each hold one share
- **RBAC:** Minimal permissions; dev access revoked when data goes live
- **No real user data in dev** — hard policy, enforce in CI

---

## Batch vs Stream Processing Boundaries

| Workload | Type | Trigger |
|----------|------|---------|
| OBD record ingest | Stream | Per record at 1Hz |
| DTC detection | Stream | Per poll cycle |
| Immediate anomaly flags (Tier 1) | Stream | Per request |
| LTFT cross-session trend | Batch | Per session end |
| LSTM/TFT training | Batch | Celery job, post-session |
| Flower FL aggregation | Batch | Nightly scheduled |
| Report generation | Async | On-demand via Celery |

---

## Storage Layout (Production NVMe 40TB)

```
/data/
  models/           ~2TB   — vLLM weights, LSTM/TFT checkpoints
  chromadb/         ~500GB — vector store
  sessions/         ~30TB  — decrypted session data (hot tier, post-TEE)
  reports/          ~5TB   — signed .acty reports, audit log
  fl_checkpoints/   ~2TB   — Flower global model versions
  redis/            ~100GB — inference cache, job queues
TrueNAS (cold):            — archived sessions, old reports, audit log cold
```

---

## OBD Session Analysis Methodology

When analyzing session data, always check in this order:

**Fuel system**
- STFT normal: ±5% | LTFT normal: ±7.5% (action) | ±10% (concern)
- LTFT trend within session: improving vs worsening as engine warms
- Cross-session LTFT history for the vehicle

**Thermal profile**
- Coolant 80°C warm-up time vs ambient
- Oil temp reaching 80°C (lags coolant 2–5 min)
- Catalyst lit-off: >300°C = active

**Charging system**
- Normal: 13.8–14.5V | Watch: <13.5V | Action: sustained <13.0V or thermal derating pattern

**Timing advance**
- Cold-idle retard (<70°C): expected
- Warm-idle retard cluster: investigate (EVAP purge, carbon, lean LTFT)
- Mid-drive retard under load: knock protection — investigate fuel quality + lean LTFT

---

## Test Vehicles

### 2024 Toyota GR86 (primary)
- FA24 2.4L NA, D-4ST dual injection, GR exhaust catback
- VIN: JF1ZNBB19P9751720 | OBD MAC: `8C:DE:52:D9:7E:D1`
- **Persistent lean LTFT: −6.5% to −8.2%** across 9+ sessions — never in normal range
- Pattern: starts near-normal (−3 to −4%), drifts lean as engine warms
- Suspect: MAF sensor thermal drift — MAF cleaned, LTFT improving toward −5.5% warm plateau
- Residual warm-idle lean pocket remains — smoke test pending
- Tuesday AM session: warm-idle timing retard cluster (8 events, −18° peak) — possible EVAP purge or early carbon

### 2022 Toyota RAV4
- 2.5L M20A-FKS, D-4ST, 288 Nm | Odometer: ~92,537 km at first session
- Fuel trims excellent: STFT +0.16%, LTFT −0.74% — healthy baseline
- Auto start-stop disabled (was causing OBD logging interruption + voltage dip to 11.65V)

### 2006 Toyota Tacoma
- 2TR-FE 2.7L four-cylinder (NOT V6)
- Battery replaced; LTFT reset to 0.00%; readiness monitors incomplete (needs 3–5 drive cycles)
- Alternator undercharging: avg 12.87V, never hit 13.5V — failing thermally
- SEC_AIR_STATUS "?" = ELM327 can't decode Toyota proprietary format, NOT a fault

### 2017 Ford Focus (guest)
- DTCs: P0043 (O2 heater), P0121 (TPS), P0047 pending (wastegate)
- STFT avg +12.7% (extreme lean) — smoke test for vacuum leak recommended

---

## Roadmap (Priority Order)

1. **Upload + auth** — Supabase auth, FastAPI `/upload`, PostgreSQL schema
2. **Android app** — Kotlin/Jetpack Compose, BT SPP OBD capture, Supabase auth, sync to `/upload`
3. **Grafana dashboards** — wire to real schema, per-session + longitudinal views
4. **Ollama → vLLM migration** — deepseek-r1:14B first, SSE streaming, webhook delivery
5. **Reporting** — recent drive report, longitudinal trends, Ed25519 signed PDF export
6. **pgVector + Timescale** — consolidate ChromaDB into PostgreSQL extensions
7. **k3s cluster** — production node setup, GPU device plugin, Ray cluster
8. **Circuit breakers + cache failure handling** — Redis stampede/penetration/breakdown/crash patterns
9. **TEE node + YubiHSM** — hardware decryption boundary + server signing key
10. **Flower FL** — federated learning coordinator, DP aggregation
11. **Merkle audit log** — public transparency root publication

**ESP32-S3 production hardware** — after Android app validates the full pipeline

---

## Business Context

- **Positioning:** Privacy-first, owner-encrypted, tamper-evident vehicle telemetry
- **Competitor gap:** Automatic/Zubie/Bouncie own user data; Acty's owner-encryption is structurally incompatible with data brokerage — genuine architectural moat
- **Revenue:** Hardware sales + verified `.acty` report fees (not data)
- **Funding:** Bootstrapped by conviction — no VC, no investor influence
- **IP:** Trade secrets now; provisional patent on hash-chain + hardware attestation when PMF validated
- **Court-admissibility path:** Hash-chain + RFC 3161 timestamps + device registry + firmware attestation + independent verification

---

## Instructions for Claude Code

- **Always treat OBD session CSVs as Acty diagnostic session data** — cross-reference vehicle history and LTFT/voltage baselines
- **Never suggest storing real user data in dev/staging** — synthetic sessions only
- **Never suggest mutable session_rows** — append-only is an architectural invariant
- **Config always in environment variables** — never hardcode ports, keys, URLs, model names
- **Stateless services always** — no in-memory request state in FastAPI or any service
- **Privacy constraints are non-negotiable** — any suggestion that routes plaintext user data through shared GPU memory without TEE isolation violates the architecture
- **Prefer pgVector over adding new ChromaDB dependencies** — consolidation is the direction
- **SSE streaming for LLM responses** — always; never return LLM output as a blocking JSON response
- **Circuit breakers on every external dependency** — FastAPI should never hang waiting for a GPU node
- **gRPC for internal high-volume service calls** — REST+JSON only for external/developer-facing APIs
- Jacob prefers **architectural-depth explanations** and honest engagement with unresolved tradeoffs over tidy answers
- When suggesting code, prefer **Kotlin/Jetpack Compose** for Android and **Python/FastAPI** for backend
- Reference the roadmap priority order when suggesting what to build next
