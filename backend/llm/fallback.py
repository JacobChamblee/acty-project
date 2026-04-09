"""
fallback.py — local Ollama/vLLM provider (no API key required).

Used when the user has no BYOK key configured. Falls back gracefully —
insight delivery is NEVER blocked because a user hasn't added a key.

Config (via environment — never hardcoded):
  CACTUS_LOCAL_INFERENCE_URL  default: http://localhost:11434
  CACTUS_LOCAL_MODEL          default: deepseek-r1:14b
"""

from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class FallbackProvider(LLMProvider):
    provider_id = "local"
    display_name = "Cactus Local (free)"
    supported_models = ["deepseek-r1:14b", "llama3.1:8b", "phi4-mini"]

    def _inference_url(self) -> str:
        return os.environ.get("CACTUS_LOCAL_INFERENCE_URL", "http://localhost:11434")

    def _model(self, model_id: str) -> str:
        if model_id and model_id in self.supported_models:
            return model_id
        return os.environ.get("CACTUS_LOCAL_MODEL", "deepseek-r1:14b")

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,  # ignored — local inference needs no key
    ) -> AsyncGenerator[str, None]:
        messages = render_prompt_messages(prompt)
        # Combine system + user for Ollama's /api/generate (non-chat endpoint)
        full_prompt = (
            messages[0]["content"] + "\n\n" + messages[1]["content"]
        )

        url = f"{self._inference_url()}/api/generate"
        payload = {
            "model": self._model(model_id),
            "prompt": full_prompt,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except Exception:
                        continue

    async def validate_key(self, api_key: str) -> bool:
        # Local inference never needs a key — just check the server is reachable
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self._inference_url()}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        return {"input_per_1m": 0.0, "output_per_1m": 0.0, "currency": "USD"}
