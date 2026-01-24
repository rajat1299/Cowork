from __future__ import annotations

import json
from typing import Any, AsyncIterator, Callable

import httpx

from app.clients.core_api import ProviderConfig


_OPENAI_COMPAT_DEFAULTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "tongyi-qianwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "sglang": "http://localhost:30000/v1",
    "lmstudio": "http://localhost:1234/v1",
    "lm-studio": "http://localhost:1234/v1",
}
_OPENAI_COMPAT_REQUIRES_ENDPOINT = {
    "openai-compatible",
    "openai-compatible-model",
    "openai-compatible-models",
    "openai-compatible-api",
}
_ANTHROPIC_NAMES = {"anthropic", "claude"}
_STREAM_OPTIONS_RETRY_HINTS = ("stream_options", "include_usage")


def _normalize_provider_name(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _resolve_openai_base(provider: ProviderConfig) -> str:
    if provider.endpoint_url:
        return provider.endpoint_url
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _OPENAI_COMPAT_DEFAULTS:
        return _OPENAI_COMPAT_DEFAULTS[normalized]
    if normalized in _OPENAI_COMPAT_REQUIRES_ENDPOINT:
        return ""
    return "https://api.openai.com/v1"


def _resolve_openai_url(endpoint_url: str | None) -> str:
    if not endpoint_url:
        return "https://api.openai.com/v1/chat/completions"
    base = endpoint_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/openai"):
        return f"{base}/chat/completions"
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _resolve_anthropic_url(endpoint_url: str | None) -> str:
    if not endpoint_url:
        return "https://api.anthropic.com/v1/messages"
    base = endpoint_url.rstrip("/")
    if base.endswith("/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def _should_retry_without_stream_options(error_text: str) -> bool:
    lowered = error_text.lower()
    return any(hint in lowered for hint in _STREAM_OPTIONS_RETRY_HINTS)


async def stream_openai_chat(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
    base = _resolve_openai_base(provider)
    if not base:
        raise RuntimeError("Endpoint URL required for OpenAI-compatible provider")
    url = _resolve_openai_url(base)
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": provider.model_type,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(2):
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    text = body.decode("utf-8", "ignore")
                    if attempt == 0 and _should_retry_without_stream_options(text):
                        payload = {key: value for key, value in payload.items() if key != "stream_options"}
                        continue
                    response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line.split(":", 1)[1].strip()
                    if data == "[DONE]":
                        return
                    event = json.loads(data)
                    if event.get("error"):
                        raise RuntimeError(event["error"].get("message", "LLM error"))
                    choices = event.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if not content:
                            content = choices[0].get("text")
                        if not content:
                            content = (choices[0].get("message") or {}).get("content")
                        if content:
                            yield content, None
                    usage = event.get("usage")
                    if usage:
                        yield None, usage
                return


async def stream_anthropic_chat(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
    url = _resolve_anthropic_url(provider.endpoint_url)
    headers = {
        "x-api-key": provider.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": provider.model_type,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    input_tokens: int | None = None
    output_tokens: int | None = None
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                data = line.split(":", 1)[1].strip()
                if not data or data == "[DONE]":
                    continue
                event = json.loads(data)
                if event.get("type") == "error":
                    error_detail = event.get("error") or {}
                    raise RuntimeError(error_detail.get("message", "LLM error"))
                event_type = event.get("type")
                if event_type == "message_start":
                    usage = (event.get("message") or {}).get("usage") or {}
                    input_tokens = usage.get("input_tokens")
                elif event_type == "content_block_start":
                    content_block = event.get("content_block") or {}
                    text = content_block.get("text")
                    if text:
                        yield text, None
                elif event_type == "content_block_delta":
                    delta = event.get("delta") or {}
                    text = delta.get("text")
                    if not text and delta.get("type") == "text_delta":
                        text = delta.get("text")
                    if text:
                        yield text, None
                elif event_type == "message_delta":
                    usage = event.get("usage") or {}
                    output_tokens = usage.get("output_tokens", output_tokens)
                    if output_tokens is not None:
                        prompt_tokens = int(input_tokens or 0)
                        completion_tokens = int(output_tokens or 0)
                        yield None, {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                        }


async def stream_chat(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _ANTHROPIC_NAMES:
        async for chunk, usage in stream_anthropic_chat(provider, messages, temperature=temperature):
            yield chunk, usage
    else:
        async for chunk, usage in stream_openai_chat(provider, messages, temperature=temperature):
            yield chunk, usage


async def collect_chat_completion(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    on_chunk: Callable[[str], None] | None = None,
) -> tuple[str, dict[str, Any] | None]:
    content_parts: list[str] = []
    usage: dict[str, Any] | None = None
    async for chunk, usage_update in stream_chat(provider, messages, temperature=temperature):
        if chunk:
            content_parts.append(chunk)
            if on_chunk:
                on_chunk(chunk)
        if usage_update:
            usage = usage_update
    return "".join(content_parts).strip(), usage
