"""
providers.py — BYOK provider registry + base class + CactusPrompt dataclass.

CactusPrompt is the contract between the pipeline and the LLM layer.
It contains ONLY pre-analyzed features — never raw OBD PID values or CSV rows.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator


# ── Structured prompt dataclass ───────────────────────────────────────────────

@dataclass
class CactusPrompt:
    """
    Pre-analyzed structured prompt — never contains raw OBD CSV data.
    Built by prompt_builder.py from pipeline tier outputs.

    Every field here corresponds to a pipeline tier output:
      vehicle_context     → DB vehicle record
      session_summary     → Tier 0 summarize_session() output
      ltft_trend          → cross-session query (Tier 0 projection)
      anomaly_flags       → Tier 1 Isolation Forest + rule engine
      fleet_pattern_match → Tier 5 FL model (None if insufficient fleet data)
      fsm_references      → Tier 2 RAG retrieval — citations with section + spec
      lstm_reconstruction → Tier 4 LSTM output (None if not yet run)
      previous_reports_summary → last 3 diagnostic_reports condensed
      user_query          → user's natural-language question
      session_count       → total sessions for this vehicle; drives UX tier logic
    """
    vehicle_context: dict                    # make, model, year, engine, odometer_km
    session_summary: dict                    # date, duration_min, drive_type, feature_aggregates
    ltft_trend: dict                         # N, values[], direction, rate_per_session
    anomaly_flags: list[dict]                # [{name, confidence, description, severity}]
    fsm_references: list[dict]               # [{section, page, spec_value, description}]
    user_query: str
    session_count: int                       # drives UX tier (1 → FSM focus, 5+ → longitudinal)
    fleet_pattern_match: dict | None = None  # {pattern_name, n_vehicles, confidence_pct, outcome}
    lstm_reconstruction: dict | None = None  # {error, threshold, status}
    previous_reports_summary: str | None = None
    extra_context: dict = field(default_factory=dict)  # provider-agnostic escape hatch


# ── Abstract base provider ─────────────────────────────────────────────────────

class LLMProvider(ABC):
    """
    All providers must implement stream_insight + validate_key.

    stream_insight MUST:
      - Use the provider's native streaming (SSE / chunked) — never buffer.
      - Accept only a CactusPrompt — never raw OBD data.
      - Yield str tokens as they arrive.

    validate_key MUST:
      - Make a cheap API call to confirm the key works (e.g., list models).
      - Return True/False — never raise for a bad key.
    """

    provider_id: str        # matches DB provider column value
    display_name: str       # shown in Android UI
    supported_models: list[str]

    @abstractmethod
    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,        # plaintext key, already decrypted by the TEE/key layer
    ) -> AsyncGenerator[str, None]:
        """Yield response tokens as they arrive from the provider."""
        ...

    @abstractmethod
    async def validate_key(self, api_key: str) -> bool:
        """Cheap key validation — used at registration time only."""
        ...

    @property
    def token_cost_estimate(self) -> dict:
        """
        Input/output cost per 1M tokens for UI transparency dashboard.
        Subclasses should override with real pricing.
        """
        return {"input_per_1m": 0.0, "output_per_1m": 0.0, "currency": "USD"}


# ── Provider registry ──────────────────────────────────────────────────────────
# Populated lazily on first import to avoid circular imports between provider files.

def _build_registry() -> dict[str, LLMProvider]:
    from .anthropic import AnthropicProvider
    from .openai_provider import OpenAIProvider
    from .google import GoogleProvider
    from .cohere import CohereProvider
    from .mistral import MistralProvider
    from .groq_provider import GroqProvider
    from .deepseek import DeepSeekProvider
    from .fallback import FallbackProvider

    providers: list[LLMProvider] = [
        AnthropicProvider(),
        OpenAIProvider(),
        GoogleProvider(),
        CohereProvider(),
        MistralProvider(),
        GroqProvider(),
        DeepSeekProvider(),
        FallbackProvider(),
    ]
    return {p.provider_id: p for p in providers}


_registry: dict[str, LLMProvider] | None = None


def PROVIDER_REGISTRY() -> dict[str, LLMProvider]:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


def get_provider(provider_id: str) -> LLMProvider:
    reg = PROVIDER_REGISTRY()
    if provider_id not in reg:
        raise ValueError(f"Unknown provider: {provider_id!r}. Available: {list(reg)}")
    return reg[provider_id]


def get_fallback_provider() -> LLMProvider:
    return PROVIDER_REGISTRY()["local"]


def list_providers() -> list[dict]:
    """Return provider metadata for the public /providers endpoint."""
    reg = PROVIDER_REGISTRY()
    return [
        {
            "provider_id": p.provider_id,
            "display_name": p.display_name,
            "supported_models": p.supported_models,
            "token_cost_estimate": p.token_cost_estimate,
            "requires_api_key": p.provider_id != "local",
        }
        for p in reg.values()
    ]
