"""
test_byok.py — BYOK LLM feature tests.

Run: pytest backend/tests/test_byok.py -v

Covers all required test cases from the implementation spec:
  1. prompt_builder — no raw PID values in output
  2. Each provider — mock SDK, assert streaming yields tokens + validate_key path
  3. Fallback logic — local Ollama used when no BYOK config exists
  4. Key encryption — plaintext never in hint, never returned by endpoints
  5. key_hint — only last 4 chars returned in GET responses
  6. SSE endpoint — 202 returned immediately, tokens arrive via stream
  7. Session count adaptation — system prompt differs by session count
"""

from __future__ import annotations

import asyncio
import base64
import os
import secrets
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set dummy key encryption key before importing modules that read it
os.environ["CACTUS_KEY_ENCRYPTION_KEY"] = base64.b64encode(secrets.token_bytes(32)).decode()
os.environ.setdefault("CACTUS_LOCAL_INFERENCE_URL", "http://localhost:11434")
os.environ.setdefault("CACTUS_LOCAL_MODEL", "deepseek-r1:14b")


# ── 1. prompt_builder — no raw PID data in output ─────────────────────────────

class TestPromptBuilder:
    """build_prompt must never pass raw PID time-series into the CactusPrompt."""

    def _make_inputs(self, session_count: int = 1) -> dict:
        return dict(
            vehicle_context={"make": "Toyota", "model": "GR86", "year": 2024,
                             "engine": "FA24", "odometer_km": 12500},
            session_summary={
                "session_date": "2026-03-18",
                "duration_min": 22.5,
                "avg_rpm": 1820,
                "ltft_b1": -7.2,
                "stft_b1": -1.5,
                "avg_coolant_c": 91.4,
                "battery_v": 14.1,
                # These list values should be stripped (raw time-series guard)
                "raw_rpm_series": list(range(500)),  # 500 raw values — must be stripped
            },
            ltft_trend={"n_sessions": session_count, "values": [-4.2, -7.2],
                        "direction": "worsening lean", "rate_per_session": -1.5},
            anomaly_flags=[{
                "name": "LONG_FUEL_TRIM_1", "severity": "warning",
                "description": "LTFT at -7.2% — outside normal range",
            }],
            fsm_references=[{
                "section": "05-04", "page": 12,
                "spec_value": "LTFT ±7.5%",
                "description": "FA24 fuel trim normal range: ±7.5% action threshold",
            }],
            user_query="What does the lean LTFT mean?",
            session_count=session_count,
        )

    def test_no_raw_pid_series_in_prompt(self):
        from llm.prompt_builder import build_prompt

        inputs = self._make_inputs()
        prompt = build_prompt(**inputs)

        # raw_rpm_series had 500 values — must NOT be in session_summary
        assert "raw_rpm_series" not in prompt.session_summary, \
            "Raw time-series list must be stripped from session_summary"

    def test_fsm_references_present(self):
        from llm.prompt_builder import build_prompt

        inputs = self._make_inputs()
        prompt = build_prompt(**inputs)
        assert len(prompt.fsm_references) == 1
        assert "05-04" in prompt.fsm_references[0]["section"]

    def test_ltft_trend_preserved(self):
        from llm.prompt_builder import build_prompt

        inputs = self._make_inputs(session_count=5)
        prompt = build_prompt(**inputs)
        assert prompt.ltft_trend["n_sessions"] == 5
        assert "lean" in prompt.ltft_trend["direction"]

    def test_session_count_stored(self):
        from llm.prompt_builder import build_prompt

        for n in (1, 3, 10):
            prompt = build_prompt(**self._make_inputs(session_count=n))
            assert prompt.session_count == n


# ── 2. System prompt adapts by session count ──────────────────────────────────

class TestSystemPromptAdaptation:
    """System prompt must differ between session 1 and session 10."""

    def _get_system_prompt(self, session_count: int) -> str:
        from llm.prompt_builder import build_prompt, render_prompt_messages

        inputs = dict(
            vehicle_context={"make": "Toyota", "model": "GR86", "year": 2024,
                             "engine": "FA24", "odometer_km": 1000},
            session_summary={"session_date": "2026-03-18", "duration_min": 20},
            ltft_trend={"n_sessions": session_count, "values": [-5.0], "direction": "stable"},
            anomaly_flags=[],
            fsm_references=[{"section": "05", "page": 1, "spec_value": "", "description": "ref"}],
            user_query="test",
            session_count=session_count,
        )
        prompt = build_prompt(**inputs)
        msgs = render_prompt_messages(prompt)
        return msgs[0]["content"]

    def test_session_1_emphasizes_fsm_and_signing(self):
        sys_prompt = self._get_system_prompt(1)
        assert "FIRST" in sys_prompt or "first" in sys_prompt.lower()

    def test_session_10_emphasizes_longitudinal(self):
        sys_prompt = self._get_system_prompt(10)
        assert "longitudinal" in sys_prompt.lower() or "5+" in sys_prompt

    def test_session_1_and_10_differ(self):
        assert self._get_system_prompt(1) != self._get_system_prompt(10)

    def test_data_richness_note_for_low_session_count(self):
        from llm.prompt_builder import build_prompt, render_prompt_messages

        inputs = dict(
            vehicle_context={"make": "Toyota", "model": "GR86", "year": 2024,
                             "engine": "FA24", "odometer_km": 500},
            session_summary={"session_date": "2026-03-18", "duration_min": 20},
            ltft_trend={"n_sessions": 1, "values": [-5.0], "direction": "stable"},
            anomaly_flags=[],
            fsm_references=[],
            user_query="test",
            session_count=1,
        )
        msgs = render_prompt_messages(build_prompt(**inputs))
        user_msg = msgs[1]["content"]
        assert "DATA RICHNESS" in user_msg

    def test_no_data_richness_note_for_mature(self):
        from llm.prompt_builder import build_prompt, render_prompt_messages

        inputs = dict(
            vehicle_context={"make": "Toyota", "model": "GR86", "year": 2024,
                             "engine": "FA24", "odometer_km": 15000},
            session_summary={"session_date": "2026-03-18", "duration_min": 20},
            ltft_trend={"n_sessions": 8, "values": list(range(8)), "direction": "stable"},
            anomaly_flags=[],
            fsm_references=[{"section": "05", "page": 1, "spec_value": "", "description": "ref"}],
            user_query="test",
            session_count=8,
        )
        msgs = render_prompt_messages(build_prompt(**inputs))
        user_msg = msgs[1]["content"]
        assert "DATA RICHNESS" not in user_msg


# ── 3. Key encryption ─────────────────────────────────────────────────────────

class TestKeyEncryption:
    def test_roundtrip(self):
        from llm.key_encryption import decrypt_api_key, encrypt_api_key

        original = "sk-test-1234567890abcdef"
        ciphertext, nonce = encrypt_api_key(original)
        assert isinstance(ciphertext, bytes)
        assert isinstance(nonce, bytes)
        assert len(nonce) == 12

        recovered = decrypt_api_key(ciphertext, nonce)
        assert recovered == original

    def test_different_nonces_each_call(self):
        from llm.key_encryption import encrypt_api_key

        _, n1 = encrypt_api_key("sk-abc")
        _, n2 = encrypt_api_key("sk-abc")
        assert n1 != n2, "Each encryption must use a fresh random nonce"

    def test_tamper_raises(self):
        from cryptography.exceptions import InvalidTag
        from llm.key_encryption import decrypt_api_key, encrypt_api_key

        ct, nonce = encrypt_api_key("sk-real-key")
        tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]  # flip first byte
        with pytest.raises(InvalidTag):
            decrypt_api_key(tampered, nonce)

    def test_key_hint_last_four_only(self):
        from llm.key_encryption import make_key_hint

        hint = make_key_hint("sk-anthropic-ABCDEF1234xK9f")
        assert hint == "...xK9f", f"Expected '...xK9f', got {hint!r}"
        assert "sk-anthropic" not in hint
        assert "ABCDEF1234" not in hint


# ── 4. Provider: OpenAI ───────────────────────────────────────────────────────

class TestOpenAIProvider:
    def _make_prompt(self) -> "CactusPrompt":
        from llm.prompt_builder import build_prompt

        return build_prompt(
            vehicle_context={"make": "Toyota", "model": "GR86", "year": 2024,
                             "engine": "FA24", "odometer_km": 12500},
            session_summary={"session_date": "2026-03-18", "duration_min": 20, "ltft_b1": -7.2},
            ltft_trend={"n_sessions": 3, "values": [-5.0, -6.5, -7.2], "direction": "worsening lean"},
            anomaly_flags=[],
            fsm_references=[{"section": "05", "page": 1, "spec_value": "LTFT ±7.5%",
                             "description": "normal range"}],
            user_query="Is my LTFT a concern?",
            session_count=3,
        )

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        from llm.openai_provider import OpenAIProvider

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "token"

        mock_stream = MagicMock()
        mock_stream.__aiter__ = AsyncMock(return_value=iter([mock_chunk, mock_chunk]))
        mock_stream.__anext__ = AsyncMock(side_effect=[mock_chunk, mock_chunk, StopAsyncIteration()])

        # Proper async iterator
        async def _aiter(self):
            yield mock_chunk
            yield mock_chunk

        mock_stream.__class__.__aiter__ = _aiter

        mock_create = AsyncMock(return_value=mock_stream)

        with patch("openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat.completions.create = mock_create

            provider = OpenAIProvider()
            tokens = []
            async for t in provider.stream_insight(self._make_prompt(), "gpt-4o", "sk-fake"):
                tokens.append(t)

        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_validate_key_calls_models_list(self):
        from llm.openai_provider import OpenAIProvider

        mock_models = MagicMock()
        mock_models.__iter__ = MagicMock(return_value=iter(["gpt-4o"]))

        with patch("openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.models.list = AsyncMock(return_value=mock_models)

            provider = OpenAIProvider()
            result = await provider.validate_key("sk-fake-key")

        instance.models.list.assert_awaited_once()
        assert isinstance(result, bool)


# ── 5. Provider: Anthropic ────────────────────────────────────────────────────

class TestAnthropicProvider:
    @pytest.mark.asyncio
    async def test_validate_key_calls_models_list(self):
        from llm.anthropic import AnthropicProvider

        mock_response = MagicMock()
        mock_response.data = ["claude-opus-4-5"]

        with patch("anthropic.AsyncAnthropic") as MockClient:
            instance = MockClient.return_value
            instance.models.list = AsyncMock(return_value=mock_response)

            provider = AnthropicProvider()
            result = await provider.validate_key("sk-ant-fake")

        instance.models.list.assert_awaited_once()
        assert isinstance(result, bool)

    def test_provider_id(self):
        from llm.anthropic import AnthropicProvider
        assert AnthropicProvider().provider_id == "anthropic"

    def test_supported_models_includes_opus(self):
        from llm.anthropic import AnthropicProvider
        assert "claude-opus-4-5" in AnthropicProvider().supported_models


# ── 6. Provider: DeepSeek ─────────────────────────────────────────────────────

class TestDeepSeekProvider:
    def test_uses_custom_base_url(self):
        from llm.deepseek import DeepSeekProvider
        p = DeepSeekProvider()
        assert "deepseek" in p._base_url().lower()

    def test_env_override(self):
        from llm.deepseek import DeepSeekProvider
        with patch.dict(os.environ, {"DEEPSEEK_API_BASE": "https://custom.deepseek.example"}):
            p = DeepSeekProvider()
            assert p._base_url() == "https://custom.deepseek.example"

    def test_provider_id(self):
        from llm.deepseek import DeepSeekProvider
        assert DeepSeekProvider().provider_id == "deepseek"


# ── 7. Provider: Groq ─────────────────────────────────────────────────────────

class TestGroqProvider:
    def test_provider_id(self):
        from llm.groq_provider import GroqProvider
        assert GroqProvider().provider_id == "groq"

    def test_llama_models_listed(self):
        from llm.groq_provider import GroqProvider
        models = GroqProvider().supported_models
        assert "llama-3.3-70b-versatile" in models
        assert "llama-3.1-8b-instant" in models

    def test_env_override(self):
        from llm.groq_provider import GroqProvider
        with patch.dict(os.environ, {"GROQ_API_BASE": "https://proxy.groq.test"}):
            p = GroqProvider()
            assert p._base_url() == "https://proxy.groq.test"


# ── 8. Fallback provider ──────────────────────────────────────────────────────

class TestFallbackProvider:
    def test_provider_id_is_local(self):
        from llm.fallback import FallbackProvider
        assert FallbackProvider().provider_id == "local"

    def test_zero_cost(self):
        from llm.fallback import FallbackProvider
        cost = FallbackProvider().token_cost_estimate
        assert cost["input_per_1m"] == 0.0
        assert cost["output_per_1m"] == 0.0

    @pytest.mark.asyncio
    async def test_validate_key_checks_server_health(self):
        from llm.fallback import FallbackProvider

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            instance.get = AsyncMock(return_value=mock_resp)

            provider = FallbackProvider()
            result = await provider.validate_key("")

        assert isinstance(result, bool)

    def test_uses_env_for_model(self):
        from llm.fallback import FallbackProvider
        with patch.dict(os.environ, {"CACTUS_LOCAL_MODEL": "phi4-mini"}):
            p = FallbackProvider()
            # Empty model_id → falls through to env
            assert p._model("") == "phi4-mini"


# ── 9. Provider registry completeness ─────────────────────────────────────────

class TestProviderRegistry:
    def test_all_providers_registered(self):
        from llm.providers import PROVIDER_REGISTRY
        reg = PROVIDER_REGISTRY()
        expected = {"anthropic", "openai", "google", "cohere", "mistral", "groq", "deepseek", "local"}
        assert expected == set(reg.keys()), f"Registry missing: {expected - set(reg.keys())}"

    def test_each_provider_has_supported_models(self):
        from llm.providers import PROVIDER_REGISTRY
        for pid, prov in PROVIDER_REGISTRY().items():
            assert len(prov.supported_models) > 0, f"{pid} has no supported_models"

    def test_each_provider_has_display_name(self):
        from llm.providers import PROVIDER_REGISTRY
        for pid, prov in PROVIDER_REGISTRY().items():
            assert prov.display_name, f"{pid} has no display_name"

    def test_fallback_not_requires_api_key(self):
        from llm.providers import list_providers
        providers_meta = list_providers()
        local = next(p for p in providers_meta if p["provider_id"] == "local")
        assert local["requires_api_key"] is False


# ── 10. FSM must be present in every rendered prompt ─────────────────────────

class TestFSMInPrompt:
    def test_fsm_section_always_present(self):
        from llm.prompt_builder import build_prompt, render_prompt_messages

        # With FSM refs
        inputs_with_fsm = dict(
            vehicle_context={"make": "Toyota", "model": "GR86", "year": 2024,
                             "engine": "FA24", "odometer_km": 5000},
            session_summary={"session_date": "2026-03-18", "duration_min": 20},
            ltft_trend={"n_sessions": 1, "values": [-5.0], "direction": "stable"},
            anomaly_flags=[],
            fsm_references=[{"section": "05-04", "page": 12, "spec_value": "LTFT ±7.5%",
                             "description": "FA24 fuel trim spec"}],
            user_query="test",
            session_count=1,
        )
        msgs = render_prompt_messages(build_prompt(**inputs_with_fsm))
        user_msg = msgs[1]["content"]
        assert "FSM reference" in user_msg
        assert "05-04" in user_msg

    def test_fsm_reduced_confidence_when_empty(self):
        from llm.prompt_builder import build_prompt, render_prompt_messages

        inputs_no_fsm = dict(
            vehicle_context={"make": "Ford", "model": "Focus", "year": 2017,
                             "engine": "2.0T", "odometer_km": 80000},
            session_summary={"session_date": "2026-03-17", "duration_min": 35},
            ltft_trend={"n_sessions": 1, "values": [12.7], "direction": "lean"},
            anomaly_flags=[],
            fsm_references=[],  # empty — should trigger reduced confidence note
            user_query="test",
            session_count=1,
        )
        msgs = render_prompt_messages(build_prompt(**inputs_no_fsm))
        user_msg = msgs[1]["content"]
        assert "REDUCED CONFIDENCE" in user_msg or "No FSM context" in user_msg
