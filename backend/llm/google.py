"""
google.py — Google Gemini BYOK provider (gemini-2.0-flash, gemini-2.5-pro).

Uses the google-genai SDK (NOT google-generativeai) because it supports
per-client API key isolation. The older genai.configure() sets global state
and is unsafe in a concurrent multi-user server.

Package: pip install google-genai>=1.0.0
Config: no env vars needed — key is passed per-client.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class GoogleProvider(LLMProvider):
    provider_id = "google"
    display_name = "Google Gemini"
    supported_models = ["gemini-2.0-flash", "gemini-2.5-pro"]

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,
    ) -> AsyncGenerator[str, None]:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=api_key)
        messages = render_prompt_messages(prompt)
        combined = messages[0]["content"] + "\n\n" + messages[1]["content"]

        async for chunk in await client.aio.models.generate_content_stream(
            model=model_id,
            contents=combined,
        ):
            if chunk.text:
                yield chunk.text

    async def validate_key(self, api_key: str) -> bool:
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            # list_models is lightweight — confirms key validity
            models = await asyncio.get_event_loop().run_in_executor(
                None, lambda: list(client.models.list())
            )
            return len(models) > 0
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        return {"input_per_1m": 0.075, "output_per_1m": 0.30, "currency": "USD"}
