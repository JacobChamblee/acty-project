"""
anthropic.py — Anthropic BYOK provider (claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5).

Anthropic uses its own SDK with a different streaming interface than OpenAI.
This validates that the LLMProvider abstraction is truly provider-agnostic.
"""

from __future__ import annotations

from typing import AsyncGenerator

from .providers import CactusPrompt, LLMProvider
from .prompt_builder import render_prompt_messages


class AnthropicProvider(LLMProvider):
    provider_id = "anthropic"
    display_name = "Anthropic (Claude)"
    supported_models = [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
    ]

    async def stream_insight(
        self,
        prompt: CactusPrompt,
        model_id: str,
        api_key: str,
    ) -> AsyncGenerator[str, None]:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)
        messages = render_prompt_messages(prompt)

        # Anthropic SDK separates system prompt from messages array
        system_content = messages[0]["content"]
        user_messages = [{"role": m["role"], "content": m["content"]} for m in messages[1:]]

        async with client.messages.stream(
            model=model_id,
            max_tokens=4096,
            system=system_content,
            messages=user_messages,
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text

    async def validate_key(self, api_key: str) -> bool:
        try:
            import anthropic
            # models.list() is the cheapest call available
            client = anthropic.AsyncAnthropic(api_key=api_key)
            models = await client.models.list()
            return len(models.data) > 0
        except Exception:
            return False

    @property
    def token_cost_estimate(self) -> dict:
        # claude-sonnet-4-5 pricing (mid-tier default)
        return {"input_per_1m": 3.00, "output_per_1m": 15.00, "currency": "USD"}
