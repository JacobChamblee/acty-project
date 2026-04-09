"""
groq_provider.py — Groq BYOK provider for Meta Llama models.

Groq provides the fastest Llama inference and uses an OpenAI-compatible API.
The user supplies a Groq API key (not a Meta key).

Config:
  GROQ_API_BASE  default: https://api.groq.com/openai/v1
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class GroqProvider(LLMProvider):
    provider_id = "groq"
    display_name = "Meta Llama (via Groq)"
    supported_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]

    def _base_url(self) -> str:
        return os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1")

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,
    ) -> AsyncGenerator[str, None]:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=api_key)
        messages = render_prompt_messages(prompt)

        stream = await client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    async def validate_key(self, api_key: str) -> bool:
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=api_key)
            models = await client.models.list()
            return len(models.data) > 0
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        return {"input_per_1m": 0.59, "output_per_1m": 0.79, "currency": "USD"}
