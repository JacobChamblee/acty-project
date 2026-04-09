"""
deepseek.py — DeepSeek BYOK provider (deepseek-chat, deepseek-reasoner).

Uses the OpenAI SDK with a custom base_url override — DeepSeek's API is
OpenAI-compatible. No separate package needed.

Config:
  DEEPSEEK_API_BASE  default: https://api.deepseek.com
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class DeepSeekProvider(LLMProvider):
    provider_id = "deepseek"
    display_name = "DeepSeek"
    supported_models = ["deepseek-chat", "deepseek-reasoner"]

    def _base_url(self) -> str:
        return os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=self._base_url())
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
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key, base_url=self._base_url())
            models = await client.models.list()
            return len(models.data) > 0
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        return {"input_per_1m": 0.27, "output_per_1m": 1.10, "currency": "USD"}
