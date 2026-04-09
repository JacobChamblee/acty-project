"""
mistral.py — Mistral AI BYOK provider.

Supported: mistral-large-latest, mistral-small-latest, mixtral-8x7b
"""

from __future__ import annotations

from typing import AsyncGenerator

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class MistralProvider(LLMProvider):
    provider_id = "mistral"
    display_name = "Mistral AI"
    supported_models = [
        "mistral-large-latest",
        "mistral-small-latest",
        "open-mixtral-8x7b",
    ]

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,
    ) -> AsyncGenerator[str, None]:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)
        messages = render_prompt_messages(prompt)
        # mistralai SDK expects dicts with "role"/"content"
        mistral_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        # stream_async is an async context manager, not a coroutine — must use async with
        async with client.chat.stream_async(
            model=model_id,
            messages=mistral_messages,
        ) as stream:
            async for chunk in stream:
                token = chunk.data.choices[0].delta.content
                if token:
                    yield token

    async def validate_key(self, api_key: str) -> bool:
        try:
            from mistralai import Mistral
            client = Mistral(api_key=api_key)
            models = await client.models.list_async()
            return len(models.data) > 0
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        return {"input_per_1m": 2.00, "output_per_1m": 6.00, "currency": "USD"}
