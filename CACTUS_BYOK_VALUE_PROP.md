# Cactus BYOK Value Proposition — Claude Code Context
> Reference this file when building any feature that touches insight generation,
> report output, LLM integration, or user-facing diagnostic content.

---

## The Core Question This File Answers

**Why is Cactus better than a user just uploading their CSV to Claude/ChatGPT directly?**

Every front-end insight card, every report layout, every API endpoint, and every LLM prompt
should be designed to express and reinforce one or more of the five differentiators below.

---

## The Five Differentiators

### 1. Longitudinal Memory — The Most Important One

A raw CSV upload to any LLM sees one session. Cactus sees all of them.

The insight is never "your LTFT is −8% right now."
It is: **"your LTFT has degraded from −4.2% to −8.1% over 9 sessions across 847 km,
at a rate consistent with MAF thermal drift seen in 23 other FA24 vehicles in the fleet."**

**Coding implications:**
- Every insight API response MUST include cross-session trend data, not just current session values
- The LLM prompt MUST include session history summary and trend direction — never send a single session in isolation
- UI insight cards MUST show trend indicators (improving / stable / worsening) alongside current values
- `session_rows` is append-only — never UPDATE or DELETE; longitudinal integrity is non-negotiable

---

### 2. FSM-Grounded Diagnostics — Factual Precision

Claude and ChatGPT know about cars generally. They do not have the GR86/BRZ factory service
manual ingested into a RAG pipeline with OEM-specified fault thresholds for the FA24 engine.

Cactus provides FSM-grounded, vehicle-specific facts — not general LLM plausibility.

**Coding implications:**
- The RAG retrieval step (ChromaDB / pgVector) MUST run before the LLM call on every insight request
- FSM citations (section, page, spec value) MUST be included in the structured prompt sent to the LLM
- LLM responses that contain specific numeric thresholds MUST be sourced from FSM context, not generated
- If FSM context is unavailable for a vehicle, the response MUST indicate reduced confidence explicitly
- Never send raw session data to the LLM — send FSM-grounded pre-analyzed features

---

### 3. Tamper-Evident Reports With Legal Standing

A ChatGPT conversation export is worthless in a dispute. A Cactus `.acty` report is not.

Every report includes:
- **Ed25519 device signature** — proves data came from this specific hardware dongle
- **Hash-chain integrity** — proves no record was modified or deleted
- **RFC 3161 timestamp** — court-admissible proof of capture time
- **Server countersignature** (YubiHSM) — Cactus attests report is unmodified
- **Verification endpoint** — `https://verify.acty-labs.com/verify/<session_id>`

**Coding implications:**
- Report generation endpoint MUST apply full signing pipeline before returning — never return unsigned reports
- The verification endpoint must be included in every generated report UI and PDF export
- Report UI should visually distinguish verified vs unverified state clearly
- Never allow report content to be edited post-signing — treat signed reports as immutable artifacts
- Signing failures MUST block report delivery, not be silently skipped

---

### 4. Privacy-Preserving Fleet Intelligence (BYOK + FL)

With BYOK, Cactus never sees plaintext user data. But Cactus CAN run Federated Learning
across the encrypted fleet — each device trains locally on its own data, and only
differential-privacy-noised gradient updates are shared.

Result: Cactus anomaly models improve from fleet-wide patterns without ever accessing
any individual's raw OBD data. No other consumer automotive platform does this.

**Coding implications:**
- Raw OBD telemetry MUST be encrypted with the user's key before leaving the device
- Only derived features (not raw PID values) are sent to the inference pipeline post-decryption
- Decryption MUST happen in the TEE node (AMD SEV-SNP) — plaintext never reaches shared GPU pool
- Federated Learning gradient updates MUST have ε ≤ 1.0 DP noise applied before aggregation
- Fleet pattern match results surfaced in UI should note they are privacy-preserving (builds trust)
- Zero-knowledge identity: session tokens are pseudonymous and rotating — never expose real user ID

---

### 5. BYOK AI API — What the LLM Actually Receives

The user brings their own Anthropic or OpenAI API key. Their key pays for the call.
But what the LLM receives is NOT a raw CSV — it is the output of the full Cactus pipeline.

**What the structured prompt contains (not raw data):**

```
System: You are a vehicle diagnostic specialist working with pre-analyzed telemetry data.

Vehicle: {make} {model} {year}, {engine}, {odometer} km
Session: {date}, {duration} min, {drive_type}

Cross-session LTFT trend ({N} sessions):
  {trend_chart_data}

Anomaly flags (Isolation Forest):
  {anomaly_name}: confidence {score}, {description}

Fleet pattern match:
  {pattern_name}: {N} vehicles, {confidence}% match, {outcome_summary}

FSM reference:
  {make} {model} service manual §{section} — {relevant_spec}

LSTM reconstruction error: {value} (threshold: {threshold}) — {status}

Previous reports summary:
  {last_3_reports_summary}

Session feature summary:
  {pre_aggregated_features}   ← NOT raw CSV rows

User question: "{user_query}"
```

**Coding implications:**
- The `/generate-report` and `/query` endpoints MUST build this structured prompt — never pass raw CSV
- Prompt construction is a first-class pipeline step, not an afterthought
- Each prompt section corresponds to a pipeline tier — missing tiers should degrade gracefully with a note
- BYOK key is used only for the external LLM API call — it never touches the signing or encryption layers
- If user has no BYOK key configured, fall back to local Ollama/vLLM — never block insight delivery entirely
- Log prompt token counts per request for cost transparency (users can see what their key is spending)

---

## Session-1 vs Mature User Experience

**Honest gap:** For a first-time user with one session, the gap between Cactus and a raw CSV
upload is smaller than it will be at session 10. Design for this explicitly:

| Session Count | Primary Differentiator to Emphasize |
|---------------|--------------------------------------|
| Session 1 | FSM-grounded facts + tamper-evident report |
| Sessions 2–4 | Trend direction emerging ("LTFT improving / worsening since last session") |
| Sessions 5+ | Full longitudinal context + fleet pattern matching |
| Fleet scale | FL-improved anomaly detection accuracy |

**Coding implications:**
- UI must show a "data richness" indicator — users should understand value grows with sessions
- Session 1 insight must still feel premium — FSM citation and signed report are available immediately
- Trend indicators should appear from session 2 onward — even a single delta is meaningful
- Never show empty states for longitudinal data — show "building history" with what's available

---

## What Never Changes Regardless of Session Count

These must be present in every insight, every report, every response:

1. **Signed report** — always, from session 1
2. **FSM grounding** — always, for every flagged condition
3. **Privacy preservation** — always, user data never leaves encrypted boundary in raw form
4. **Verification link** — always included in report output

---

## Anti-Patterns — Never Do These

- ❌ Send raw CSV rows to the LLM API
- ❌ Return unsigned or partially-signed reports
- ❌ Build single-session insight views with no path to longitudinal context
- ❌ Allow plaintext session data to reach shared GPU memory without TEE decryption boundary
- ❌ Store real user OBD data in dev/staging environments
- ❌ Hardcode API keys, model names, or service URLs — all config via environment variables
- ❌ Block insight delivery if BYOK key is missing — degrade to local model gracefully
- ❌ Mutate `session_rows` — append-only is an architectural invariant
- ❌ Return LLM responses synchronously for Tier 3+ — use SSE streaming always
