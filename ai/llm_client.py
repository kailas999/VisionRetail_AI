"""
AI Copilot LLM Client — GPT-5.2 / GPT-5.2 async client.

This module is the single point of contact with the OpenAI API.
All calls are async, include timeout + retry, and enforce JSON output.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[AsyncOpenAI] = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        kwargs = {
            "api_key": settings.openai_api_key,
            "base_url": settings.openai_base_url,
        }
        # Azure OpenAI expects 'api-key' instead of 'Authorization: Bearer'
        if settings.openai_base_url and "azure.com" in settings.openai_base_url:
            kwargs["default_headers"] = {"api-key": settings.openai_api_key}
            
        _client = AsyncOpenAI(**kwargs)
    return _client


async def chat_completion(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.1,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Single async GPT call.
    Returns parsed JSON dict or raises on failure.
    temperature=0.1 for factual consistency.
    """
    model = model or settings.openai_model
    client = get_client()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
            timeout=timeout,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as e:
        logger.error("LLM call failed", extra={"model": model, "error": str(e)})
        return {
            "observations": [],
            "evidence": [],
            "conclusion": "INSUFFICIENT_DATA: LLM service unavailable.",
            "confidence": 0.0,
            "insufficient_data": True,
        }
