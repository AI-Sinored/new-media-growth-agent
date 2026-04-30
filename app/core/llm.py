from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings


class LLMClient:
    """Small adapter. If no API key is configured, caller can use rule-based fallback."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.available = bool(self.settings.openai_api_key)

    async def json_completion(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.available:
            return None
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.llm_timeout_seconds)
            response = await client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception:
            return None
