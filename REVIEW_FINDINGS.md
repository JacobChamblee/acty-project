# Acty/Cactus — Code Review Findings
> Session 1: Security, privacy, and invariant review of `backend/` and `hardware/`
> Scope: all Python files under `backend/api/`, `backend/ml/`, `hardware/`, root-level capture scripts

---

## 1. SECURITY / PRIVACY VIOLATIONS (HARD VIOLATIONS)

---

### [HIGH] H1 — Raw PID data stored unencrypted in `session_rows`
- **File:** [backend/api/server.py:819-840](backend/api/server.py#L819-L840)
- **Status:** HARD VIOLATION — "no plaintext PID data at rest on server"
- **Description:** `_persist_session()` builds a `pid_values` dict of raw float values from every CSV row and writes it to `session_rows.pid_values` as plain JSONB with no encryption. Every OBD-II reading (RPM, speed, fuel trims, oil temp, etc.) is stored in cleartext in PostgreSQL. If the DB is breached, all per-row sensor data is exposed without the owner's key.
- **Code:**
  ```python
  pid_values = { c: float(row_dict[c]) ... for c in pid_cols ... }   # line 819-827
  raw_str = f"{seq}|{ts_dt}|{json.dumps(pid_values,...)}|{prev_hash}"  # line 835
  batch.append((..., json.dumps(pid_values), ...))                     # line 840
  ```
- **Fix:** Encrypt `pid_values` with the owner's key (AES-256-GCM, keyed per-user) before persisting, matching the `.acty` binary format. Or remove row-level storage and rely solely on session-level aggregates (which contain no raw values).
- **UNTESTED:** No test validates that `pid_values` is not written in plaintext.

---

### [HIGH] H2 — `/insights` endpoint has no session ownership check
- **File:** [backend/api/server.py:885-938](backend/api/server.py#L885-L938)
- **Status:** HARD VIOLATION — any authenticated user can read any other user's session
- **Description:** `GET /insights?session=<filename>` accepts an arbitrary filename and reads it from `CSV_DIR` with only JWT authentication — no ownership check against the DB. In contrast, `GET /sessions/{filename}` (line 1024) correctly validates ownership before calling `insights()`. Since `insights()` is a public FastAPI route AND an internal helper, the direct route bypasses all access control.
- **Impact:** Attacker with any valid Supabase account can enumerate other users' session filenames and call `/insights?session=<victim_file>` to receive full PID statistics, anomaly flags, and fuel trim trends.
- **Fix:** Add ownership check to the `/insights` endpoint itself, not only to `session_detail`. Extract ownership validation into a shared helper used by both routes.
- **UNTESTED:** `test_e2e_pipeline.py` calls `/insights` via `app_with_auth` which bypasses ownership entirely.

---

### [HIGH] H3 — `session_detail` ownership check silently bypassed on DB exception
- **File:** [backend/api/server.py:1056-1061](backend/api/server.py#L1056-L1061)
- **Status:** HARD VIOLATION — exception in ownership check is swallowed, data is served
- **Description:** If the ownership DB query throws any non-HTTP exception (connection reset, timeout, asyncpg error), the code logs a warning and proceeds to serve the file to whoever asked for it.
- **Code:**
  ```python
  except Exception as exc:
      print(f"[session_detail] ownership check failed: {exc} — proceeding")
  return await insights(session=filename, user=user)   # runs regardless
  ```
- **Impact:** An attacker who can cause a transient DB failure (e.g., exhaust the connection pool) at the moment of their request can read any session file.
- **Fix:** Replace `— proceeding` with `raise HTTPException(503, "Ownership check unavailable")`. Never serve data when authorization cannot be confirmed.
- **UNTESTED:** No test for this error path.

---

### [HIGH] H4 — RAG server has no authentication on any endpoint
- **File:** [backend/ml/rag/server/rag_server.py:32-108](backend/ml/rag/server/rag_server.py#L32-L108)
- **Status:** HARD VIOLATION — unauthenticated access to factory service manual contents
- **Description:** All four RAG server endpoints (`/health`, `/retrieve`, `/context`, `/query`) accept requests with no JWT or API-key check. The `/retrieve` and `/query` endpoints expose FSM (Factory Service Manual) reference content to anyone who can reach port 8766 on the 4U server.
- **Impact:** FSM procedure content, torque specs, and repair step sequences are publicly readable if the server is on a reachable network segment. The `/query` endpoint also proxies queries to Ollama (port 11434), creating an unauthenticated LLM gateway.
- **Fix:** Add a shared secret or mTLS requirement to `/retrieve`, `/context`, and `/query`. At minimum, require an `X-Internal-Token` header matching `RAG_INTERNAL_TOKEN` env var, validated in a FastAPI dependency.
- **UNTESTED:** No test for RAG server auth.

---

## 2. BROKEN INVARIANTS

---

### [HIGH] I1 — Hash-chain does not include `session_id` in digest input
- **File:** [backend/api/server.py:835](backend/api/server.py#L835)
- **Status:** BROKEN INVARIANT — hash-chain integrity is not session-scoped
- **Description:** The hash input at each row is `f"{seq}|{ts_dt}|{json.dumps(pid_values)}|{prev_hash}"`. Because `session_id` is absent, an attacker can splice rows from one session into another: if two sessions share the same `seq`, `ts_dt`, and `pid_values` values, the resulting hashes are identical. The chain is tamper-evident within a session but not across sessions.
- **Invariant:** "SHA256(seq + timestamp + pids + prev_hash) → Ed25519"
- **Fix:** Change `raw_str` to include `session_id`:
  ```python
  raw_str = f"{session_id}|{seq}|{ts_dt}|{json.dumps(pid_values,...)}|{prev_hash or ''}"
  ```
- **UNTESTED:** No test validates cross-session row forgery protection.

---

### [MEDIUM] I2 — Hash-chain first row uses empty string as `prev_hash` sentinel
- **File:** [backend/api/server.py:816,835](backend/api/server.py#L816)
- **Status:** BROKEN INVARIANT — chain start is not cryptographically bound to the session
- **Description:** The first row is initialized with `prev_hash = None` and the hash input uses `prev_hash or ''` (empty string). This means any attacker who knows `seq=0`, the timestamp, and the PID values can reconstruct row 0's `record_hash` without knowledge of any session secret.
- **Fix:** Initialize `prev_hash` to `hashlib.sha256(f"START|{session_id}|{ts_of_first_row}".encode()).hexdigest()` so the chain root is bound to this specific session at a known time.
- **UNTESTED:** No test validates that the chain root cannot be spoofed.

---

## 3. LOGIC BUGS

---

### [MEDIUM] B1 — Path traversal via unsanitized filename in `/upload`
- **File:** [backend/api/server.py:1084](backend/api/server.py#L1084)
- **Description:** The upload endpoint writes the file to `CSV_DIR / file.filename` without stripping path separators. A client can upload a file named `../../etc/cron.d/backdoor` and write it outside the CSV directory.
- **Code:**
  ```python
  csv_path = CSV_DIR / file.filename   # no sanitization
  csv_path.write_bytes(contents)
  ```
- **Fix:**
  ```python
  safe_name = Path(file.filename).name   # strip directory components
  if not re.match(r'^acty_obd_[\w\-\.]+\.csv$', safe_name):
      raise HTTPException(400, "Invalid filename format")
  csv_path = CSV_DIR / safe_name
  ```
- **UNTESTED:** No test uploads a file with `../` in the name.

---

### [MEDIUM] B2 — BYOK API keys transmitted in plaintext (HTTPS not enforced)
- **File:** [backend/api/routers/llm_config.py:68-70](backend/api/routers/llm_config.py#L68-L70)
- **Description:** The `RegisterKeyRequest` model accepts the `api_key` as a plaintext string. The in-code comment acknowledges "The Android client MUST use HTTPS" but no enforcement exists in the API, CORS config, or deployment layer. If a client connects over HTTP (e.g., during local dev or misconfigured deploy), the key is transmitted and logged in cleartext.
- **Fix:** Add a startup check or middleware that rejects requests on non-HTTPS connections, or switch to client-side pre-encryption (TEE architecture noted as future work in the TODO comment).
- **UNTESTED:** No test validates HTTPS-only key registration.

---

### [LOW] B3 — `CSV_DIR` defined independently in three modules
- **Files:** [backend/api/server.py:30](backend/api/server.py#L30), [backend/api/routers/sessions_router.py:31](backend/api/routers/sessions_router.py#L31), [backend/api/routers/ollama_router.py:46](backend/api/routers/ollama_router.py#L46)
- **Description:** All three read `ACTY_CSV_DIR` from the environment independently. If the default value ever changes or validation is added (see B1), three places must be updated.
- **Fix:** Define `CSV_DIR` once in `server.py` and import it in the routers.

---

### [LOW] B4 — Vehicle make/model/year hardcoded in `_persist_session` and `_compute_trip_report`
- **Files:** [backend/api/server.py:689](backend/api/server.py#L689), [backend/api/server.py:580](backend/api/server.py#L580)
- **Description:** `"Toyota", "GR86", 2023, "FA24"` are hardcoded in the DB insert. `"vehicle": "GR86"` is hardcoded in the trip report output. These values are not derived from the CSV or from the authenticated user's vehicle profile.
- **Fix:** Pull make/model/year from the `vehicles` table via `vehicle_id`, or accept them as upload metadata.

---

### [LOW] B5 — `SUPABASE_JWT_SECRET` missing at startup only produces a warning from BYOK check, not from auth check
- **File:** [backend/api/server.py:84-92](backend/api/server.py#L84-L92)
- **Description:** Startup validates `CACTUS_KEY_ENCRYPTION_KEY` but not `SUPABASE_JWT_SECRET`. The JWT secret is only checked at request time (deps.py:29-33), returning 503 per-request. The server starts cleanly with no JWT secret, passes health checks, then rejects every authenticated request at runtime.
- **Fix:** Add a `SUPABASE_JWT_SECRET` presence check to the lifespan handler and raise on startup if missing.

---

## 4. STYLE / CLEANUP

---

### [LOW] C1 — Inconsistent exception handling in `_persist_session`
- **File:** [backend/api/server.py:852](backend/api/server.py#L852)
- **Description:** `except Exception as e: print(...)` is the only error reporting for the entire persistence block. Errors are silently swallowed after the print. Other routers (e.g., `vehicles_router.py`) use `log.error()` and re-raise as 503. Standardize on `log.warning()` (since persist is best-effort) but do not use bare `print()` in production code.

---

### [LOW] C2 — Magic numbers in anomaly thresholds not documented
- **File:** [backend/api/server.py:36-46](backend/api/server.py#L36-L46)
- **Description:** Threshold values (e.g., `COOLANT_TEMP warn=100, crit=108`) are hardcoded with no source attribution. These were presumably calibrated for the GR86/FA24 — that context should be preserved or the values should be env-configurable.

---

### [LOW] C3 — `anomaly.py` note about removed LSTM is accurate but the docstring claims "Stage 2"
- **File:** [backend/ml/pipeline/anomaly.py:1-9](backend/ml/pipeline/anomaly.py#L1-L9)
- **Description:** The docstring calls this "Stage 2: Anomaly Detection" but per the pipeline invariant the order is: rules → ensemble → RAG → LLM → LSTM → FL. Isolation Forest is being used as both the rule-based (stage 1) and ensemble (stage 2) component in the current implementation. The stage labeling is misleading.

---

## 5. UNTESTED FUNCTIONS

| Function | File | Notes |
|---|---|---|
| `_build_cactus_prompt()` | [insights.py:189](backend/api/routers/insights.py#L189) | RAG call path never tested; mocked in e2e suite |
| `_persist_session()` hash-chain logic | [server.py:803-850](backend/api/server.py#L803) | Only tested with `_persist_session` fully mocked; hash construction never executed in tests |
| RAG server endpoints | [rag_server.py:32-108](backend/ml/rag/server/rag_server.py#L32) | Zero tests |
| `run_isolation_forest()` edge: all-NaN cols | [anomaly.py:42](backend/ml/pipeline/anomaly.py#L42) | Min-samples path tested but not NaN-fill edge case |
| `hardware/acty_obd_capture.py` — full file | [hardware/acty_obd_capture.py](hardware/acty_obd_capture.py) | No unit tests at all |
| `capture_sync.py` — full file | [capture_sync.py](capture_sync.py) | No unit tests at all |
| `/upload` filename sanitization | [server.py:1064-1106](backend/api/server.py#L1064) | No test for path traversal |
| `session_detail` ownership bypass on exception | [server.py:1056-1061](backend/api/server.py#L1056) | No test for the exception path |

---

## Summary

| Severity | Count | Items |
|---|---|---|
| **HIGH** | 4 | H1 (raw PID unencrypted), H2 (insights no ownership), H3 (ownership bypass on exception), H4 (RAG no auth) |
| **MEDIUM** | 3 | I1 (hash-chain no session_id), B1 (path traversal upload), B2 (BYOK plaintext) |
| **LOW/MEDIUM** | 1 | I2 (hash-chain empty sentinel) |
| **LOW** | 6 | B3–B5, C1–C3 |

**Recommended action order for Session 2:**
1. Fix H2: add ownership check to `/insights` endpoint
2. Fix H3: raise 503 instead of proceeding on DB exception in `session_detail`
3. Fix H4: add shared-secret auth to RAG server
4. Fix B1: sanitize filename in `/upload`
5. Fix I1: add `session_id` to hash-chain input
6. Fix I2: initialize `prev_hash` with session-start sentinel

REVIEW COMPLETE — 41 files reviewed, 14 findings (4 HIGH, 4 MEDIUM, 6 LOW)
