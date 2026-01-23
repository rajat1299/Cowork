from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.clients.core_api import ProviderConfig


def _resolve_openai_url(endpoint_url: str | None) -> str:
    if not endpoint_url:
        return "https://api.openai.com/v1/chat/completions"
    base = endpoint_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


async def stream_openai_chat(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
    url = _resolve_openai_url(provider.endpoint_url)
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider.model_type,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if event.get("error"):
                    raise RuntimeError(event["error"].get("message", "LLM error"))
                choices = event.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content, None
                usage = event.get("usage")
                if usage:
                    yield None, usage
