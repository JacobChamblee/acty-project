# Claude Code Prompt — Cactus BYOK Multi-Provider LLM Feature

## How to Use This Prompt

Load these files into your Claude Code session before starting:
```
@CACTUS_CODE_BEST_PRACTICES.md
@CACTUS_BYOK_VALUE_PROP.md
@CACTUS_BYOK_IMPLEMENTATION_PROMPT.md
```

Then paste everything below the horizontal rule into Claude Code.

---

## Prompt Starts Here

You are implementing the **BYOK (Bring Your Own Key) multi-provider LLM feature** for the
Cactus platform. You have already loaded `CACTUS_CODE_BEST_PRACTICES.md` and
`CACTUS_BYOK_VALUE_PROP.md` as project context. All architectural constraints, privacy
invariants, and anti-patterns defined in those files apply to every line of code you write here.

---

### What You Are Building

A provider-agnostic LLM abstraction layer that allows Cactus users to supply their own API
key for any supported provider. The key is used only at Tier 3 (LLM synthesis) in the insight
pipeline. All upstream pipeline stages (Tier 0–2: cache, CPU ensemble, RAG retrieval) and all
downstream stages (Tier 4–5: LSTM, FL) are unaffected by provider choice.

The BYOK key is the user's credential — it NEVER touches signing, encryption, or any
privacy-critical layer. If no BYOK key is configured, fall back to local Ollama/vLLM silently.

---

### Supported Providers

Implement support for all seven of the following. Each has a distinct API surface:

| Provider | Models to Support | API Style |
|----------|-------------------|-----------|
| **Anthropic** | claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5 | Anthropic SDK, SSE native |
| **OpenAI** | gpt-4o, gpt-4o-mini, o3, o4-mini | OpenAI SDK, SSE native |
| **Google** | gemini-2.0-flash, gemini-2.5-pro | google-generativeai SDK, SSE native |
| **Cohere** | command-r-plus, command-r | cohere SDK, streaming supported |
| **Mistral AI** | mistral-large-latest, mistral-small-latest, mixtral-8x7b | mistralai SDK, SSE native |
| **Meta (Llama)** | llama-3.3-70b-versatile, llama-3.1-8b-instant | Via Groq API (fastest Llama hosting) |
| **DeepSeek** | deepseek-chat, deepseek-reasoner | OpenAI-compatible API, SSE native |

For Meta/Llama: use Groq as the API provider (groq.com) — it provides the fastest Llama
inference and uses an OpenAI-compatible interface. The user supplies a Groq API key.

---

### Backend Implementation

#### 1. Database Schema — `user_llm_configs` Table

Add a new PostgreSQL table. Write the migration file:

```sql
CREATE TABLE user_llm_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL,          -- 'anthropic' | 'openai' | 'google' |
                                             -- 'cohere' | 'mistral' | 'groq' | 'deepseek'
    model_id VARCHAR(128) NOT NULL,          -- exact model string for the provider API
    encrypted_api_key BYTEA NOT NULL,        -- AES-256-GCM encrypted with user's data key
    key_iv BYTEA NOT NULL,                   -- GCM IV for this encryption
    key_hint VARCHAR(8),                     -- last 4 chars of key for UI display e.g. "...xK9f"
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    UNIQUE(user_id, provider)                -- one active config per provider per user
);

CREATE INDEX idx_user_llm_configs_user_id ON user_llm_configs(user_id);
```

**Critical:** The `encrypted_api_key` is encrypted with the user's own AES-256-GCM data key
(same key used for session data encryption). Cactus never stores or sees the plaintext API key.
Decryption happens at request time in the TEE node boundary, same as session data.

---

#### 2. Provider Abstraction Layer

Create `acty_api/llm/providers.py`:

```
acty_api/
  llm/
    __init__.py
    providers.py        ← provider registry + base class
    anthropic.py        ← Anthropic provider
    openai_provider.py  ← OpenAI provider
    google.py           ← Google Gemini provider
    cohere.py           ← Cohere provider
    mistral.py          ← Mistral provider
    groq_provider.py    ← Groq/Llama provider
    deepseek.py         ← DeepSeek provider
    fallback.py         ← local Ollama/vLLM fallback
    prompt_builder.py   ← shared Cactus structured prompt construction
```

**Base class contract** (`providers.py`):

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from dataclasses import dataclass

@dataclass
class CactusPrompt:
    """
    Pre-analyzed structured prompt — never contains raw OBD CSV data.
    Built by prompt_builder.py from pipeline tier outputs.
    """
    vehicle_context: dict          # make, model, year, engine, odometer
    session_summary: dict          # date, duration, drive_type, feature_aggregates
    ltft_trend: dict               # N sessions, values, direction, rate
    anomaly_flags: list[dict]      # from Isolation Forest output
    fleet_pattern_match: dict | None  # from FL model, may be None if insufficient fleet data
    fsm_references: list[dict]     # from RAG retrieval — section, spec, threshold
    lstm_reconstruction: dict | None  # error value, threshold, status; None if not yet run
    previous_reports_summary: str | None  # last 3 reports condensed
    user_query: str
    session_count: int             # total sessions for this vehicle — drives UX tier


class LLMProvider(ABC):
    provider_id: str               # matches DB provider column
    display_name: str
    supported_models: list[str]

    @abstractmethod
    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,              # plaintext key, already decrypted by TEE layer
    ) -> AsyncGenerator[str, None]:
        """
        Yield response tokens as they arrive.
        Must use provider's native streaming — never buffer full response.
        Must NOT receive raw OBD data — only CactusPrompt fields.
        """
        ...

    @abstractmethod
    async def validate_key(self, api_key: str) -> bool:
        """
        Lightweight key validation — make a minimal API call to confirm key works.
        Do not make this expensive. Used at key registration time only.
        """
        ...

    @property
    def token_cost_estimate(self) -> dict:
        """
        Return input/output cost per 1M tokens for display in UI.
        Used for transparency dashboard — users see what their key is spending.
        """
        return {"input_per_1m": 0.0, "output_per_1m": 0.0, "currency": "USD"}
```

---

#### 3. Prompt Builder

Create `acty_api/llm/prompt_builder.py`. This is a critical file — it is the reason Cactus
insight is better than a raw CSV upload to any LLM. Every section must be populated from
upstream pipeline outputs, not from raw session data.

The builder must:
- Accept outputs from Tier 1 (anomaly flags), Tier 2 (RAG context), cross-session trend data
- Construct a `CactusPrompt` dataclass
- Adapt the system prompt text based on `session_count` (session 1 emphasizes FSM + signing;
  session 5+ emphasizes longitudinal trends + fleet patterns)
- Never include raw PID values or CSV rows in the prompt
- Include FSM citations with section numbers and OEM-specified thresholds
- Include a `[DATA RICHNESS]` note when session count is low (< 3) explaining that trend
  analysis improves with more sessions

---

#### 4. FastAPI Endpoints

Add to `acty_api/routers/llm_config.py`:

```
POST   /api/v1/llm-config              — register a new provider key
GET    /api/v1/llm-config              — list user's configured providers (key_hint only, never plaintext)
DELETE /api/v1/llm-config/{provider}   — remove a provider config
POST   /api/v1/llm-config/{provider}/validate — validate key without saving
GET    /api/v1/llm-config/providers    — list all supported providers + models (no auth required)
```

Add to `acty_api/routers/insights.py` — update existing generate endpoint:

```
POST   /api/v1/insights/generate       — generate insight, provider selected by user
GET    /api/v1/insights/stream/{job_id} — SSE stream endpoint for Tier 3 response
```

The generate endpoint must:
1. Accept optional `provider` and `model_id` params
2. If provider specified → decrypt user's key for that provider → use BYOK path
3. If no provider specified → use local Ollama/vLLM fallback
4. Return `202 Accepted` with `job_id` immediately — never block
5. Stream via SSE on the `/stream/{job_id}` endpoint

---

#### 5. Environment Variables

Add to `.env.example` and document in README. These are the fallback local inference config,
not user BYOK keys — user keys live in the DB encrypted:

```bash
# Local fallback inference (used when user has no BYOK key configured)
CACTUS_LOCAL_INFERENCE_URL=http://localhost:11434   # Ollama in dev
CACTUS_LOCAL_MODEL=deepseek-r1:14b

# Key encryption — used to encrypt user BYOK keys at rest
# Must be 32 bytes, base64-encoded, stored in secrets manager not .env in prod
CACTUS_KEY_ENCRYPTION_KEY=

# Provider API base URLs (override for self-hosted / proxy setups)
DEEPSEEK_API_BASE=https://api.deepseek.com
GROQ_API_BASE=https://api.groq.com/openai/v1
```

---

#### 6. Dependencies

Add to `requirements.txt`:

```
anthropic>=0.40.0
openai>=1.50.0
google-generativeai>=0.8.0
cohere>=5.0.0
mistralai>=1.0.0
groq>=0.11.0
# deepseek uses openai SDK with custom base_url — no separate package needed
```

---

### Android Implementation (Kotlin/Jetpack Compose)

#### Settings Screen — BYOK Configuration UI

Create `ui/settings/LLMSettingsScreen.kt`. Requirements:

**Provider selection:**
- Scrollable list of all 7 providers with logo/icon, display name, model dropdown
- Each provider card shows: connected (green indicator) / not configured (grey) state
- Show `key_hint` (e.g. "...xK9f") when configured — never show full key
- "Add Key" / "Remove" / "Test Connection" actions per provider

**Key input:**
- Masked text field (password input) for API key entry
- "Test before saving" — calls `/api/v1/llm-config/{provider}/validate` before storing
- On save: key is encrypted on-device with user's data key before sending to backend
- Never send plaintext API key over the network — encrypt client-side first

**Active provider selector:**
- Single selector for which provider to use for insight generation
- Falls back to "Cactus Local (free)" if none configured
- Show estimated cost per insight request based on `token_cost_estimate`

**Cost transparency panel:**
- Running total of approximate token spend per provider this month
- Pulled from `/api/v1/llm-config` response which includes `last_used_at` and usage estimates
- Makes BYOK feel empowering, not scary

#### Insight Screen — Provider Badge

On every insight card and report view, show a small provider badge:
- "Powered by Claude" / "Powered by GPT-4o" / "Powered by Cactus Local" etc.
- Tapping the badge opens a brief explanation of what the LLM received (not raw data —
  pre-analyzed features) — reinforces the privacy + value prop in the UI itself

---

### Implementation Order

Do these in sequence. Do not proceed to the next step until the current one compiles and passes
its tests:

1. **Database migration** — `user_llm_configs` table + indexes
2. **Base provider class + `CactusPrompt` dataclass** — no provider implementations yet
3. **`prompt_builder.py`** — this is the most important file; get it right before any provider
4. **Fallback provider** (local Ollama/vLLM) — validates the streaming pipeline end-to-end
5. **OpenAI provider** — most commonly used, good reference implementation
6. **DeepSeek provider** — uses OpenAI SDK with `base_url` override, trivial after OpenAI
7. **Anthropic provider** — different SDK, validates abstraction layer flexibility
8. **Groq provider (Llama)** — OpenAI-compatible, validates Groq base_url pattern
9. **Mistral provider**
10. **Google provider** — most different SDK, validates abstraction holds
11. **Cohere provider**
12. **FastAPI endpoints** — wire everything together
13. **Android settings screen** — provider list, key input, validation flow
14. **Android insight screen** — provider badge, cost transparency panel
15. **Integration tests** — mock each provider, verify prompt never contains raw PID data

---

### Testing Requirements

Write tests for each of the following before considering any step complete:

- `prompt_builder.py` — assert output `CactusPrompt` contains NO raw PID values from input
- Each provider — mock the SDK, assert streaming yields tokens, assert `validate_key` calls
  the correct minimal endpoint
- Fallback logic — assert local Ollama is used when no BYOK config exists for user
- Key encryption — assert plaintext key is never logged, never returned by any endpoint
- `key_hint` — assert only last 4 chars returned in GET responses
- SSE endpoint — assert `202 Accepted` returned immediately, tokens arrive via stream
- Session count adaptation — assert system prompt differs between session_count=1 and
  session_count=10 (different emphasis as documented in BYOK value prop)

---

### Hard Constraints — Repeat From Context Files

These apply to every file you touch in this feature:

- ❌ Never log or return a plaintext API key anywhere in the stack
- ❌ Never send raw OBD CSV rows to any LLM provider — only `CactusPrompt` derived fields
- ❌ Never block on LLM response — always `202 Accepted` + SSE stream
- ❌ Never store `encrypted_api_key` without the corresponding `key_iv`
- ❌ Never hardcode provider API base URLs — all via environment variables
- ❌ Never return a 500 if BYOK provider fails — degrade to local fallback and note it in response
- ✅ Every provider implementation must implement both `stream_insight` and `validate_key`
- ✅ `prompt_builder.py` must include FSM citations in every prompt regardless of provider
- ✅ Signing pipeline is completely separate from BYOK — a signed report is signed by Cactus
  infrastructure regardless of which LLM generated the narrative text
- ✅ Config via environment variables only — no hardcoded values anywhere
