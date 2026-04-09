"""
openai_provider.py — OpenAI BYOK provider (gpt-4o, gpt-4o-mini, o3, o4-mini).

Reference implementation — the simplest provider after DeepSeek.
All other OpenAI-SDK-compatible providers (DeepSeek, Groq) follow this pattern.
"""

from __future__ import annotations

from typing import AsyncGenerator

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class OpenAIProvider(LLMProvider):
    provider_id = "openai"
    display_name = "OpenAI"
    supported_models = ["gpt-4o", "gpt-4o-mini", "o3", "o4-mini"]

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
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
            client = AsyncOpenAI(api_key=api_key)
            models = await client.models.list()
            return len(models.data) > 0
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        # gpt-4o pricing as of early 2025 (update when pricing changes)
        return {"input_per_1m": 2.50, "output_per_1m": 10.00, "currency": "USD"}
