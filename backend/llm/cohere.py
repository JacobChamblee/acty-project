"""
cohere.py — Cohere BYOK provider (command-r-plus, command-r).
"""

from __future__ import annotations

from typing import AsyncGenerator

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class CohereProvider(LLMProvider):
    provider_id = "cohere"
    display_name = "Cohere"
    supported_models = ["command-r-plus", "command-r"]

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,
    ) -> AsyncGenerator[str, None]:
        import cohere

        client = cohere.AsyncClientV2(api_key=api_key)
        messages = render_prompt_messages(prompt)
        # Cohere V2 chat uses same role/content format as OpenAI
        cohere_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        async for event in client.chat_stream(
            model=model_id,
            messages=cohere_messages,
        ):
            if event.type == "content-delta":
                token = event.delta.message.content.text if event.delta.message else None
                if token:
                    yield token

    async def validate_key(self, api_key: str) -> bool:
        try:
            import cohere
            client = cohere.AsyncClientV2(api_key=api_key)
            # List models is cheap for Cohere V2
            response = await client.models.list()
            return len(response.models) > 0
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        return {"input_per_1m": 2.50, "output_per_1m": 10.00, "currency": "USD"}
