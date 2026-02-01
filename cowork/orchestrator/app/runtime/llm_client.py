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


def _merge_extra_params(
    payload: dict[str, Any],
    extra_params: dict[str, Any] | None,
    protected_keys: set[str] | None = None,
) -> dict[str, Any]:
    if not extra_params:
        return payload
    blocked = protected_keys or {"model", "messages", "stream"}
    for key, value in extra_params.items():
        if key in blocked:
            continue
        payload[key] = value
    return payload


def _messages_to_text(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = message.get("role") or "user"
        content = message.get("content") or ""
        parts.append(f"{role}: {content}")
    return "\n".join(parts).strip()


def _messages_to_gemini_contents(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    system_parts: list[str] = []
    for message in messages:
        role = message.get("role") or "user"
        content = message.get("content") or ""
        if role == "system":
            system_parts.append(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})
    if system_parts:
        system_text = "\n".join(system_parts).strip()
        if contents and contents[0]["role"] == "user":
            contents[0]["parts"][0]["text"] = f"{system_text}\n\n{contents[0]['parts'][0]['text']}"
        else:
            contents.insert(0, {"role": "user", "parts": [{"text": system_text}]})
    return contents


def _should_use_openai_responses(extra_params: dict[str, Any] | None) -> bool:
    if not extra_params:
        return False
    tools = extra_params.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict) and tool.get("type") == "web_search":
                return True
    return False


def _resolve_openai_responses_url(endpoint_url: str | None) -> str:
    if not endpoint_url:
        return "https://api.openai.com/v1/responses"
    base = endpoint_url.rstrip("/")
    if base.endswith("/responses"):
        return base
    if base.endswith("/v1"):
        return f"{base}/responses"
    return f"{base}/v1/responses"


def _resolve_gemini_url(endpoint_url: str | None, model_type: str) -> str:
    if not endpoint_url:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model_type}:generateContent"
    base = endpoint_url.rstrip("/")
    if ":generateContent" in base:
        return base
    if base.endswith("/v1beta"):
        return f"{base}/models/{model_type}:generateContent"
    if base.endswith("/models"):
        return f"{base}/{model_type}:generateContent"
    return f"{base}/models/{model_type}:generateContent"


def _extract_openai_responses_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            content = item.get("content") or []
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        return text
    return ""


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list):
        return ""
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                return part["text"]
    return ""


def _extract_gemini_usage(payload: dict[str, Any]) -> dict[str, Any] | None:
    usage = payload.get("usageMetadata") or {}
    if not isinstance(usage, dict):
        return None
    prompt_tokens = usage.get("promptTokenCount")
    completion_tokens = usage.get("candidatesTokenCount")
    total_tokens = usage.get("totalTokenCount")
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens
    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None
    return {
        "prompt_tokens": prompt_tokens or 0,
        "completion_tokens": completion_tokens or 0,
        "total_tokens": total_tokens or 0,
    }


async def stream_openai_chat(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    extra_params: dict[str, Any] | None = None,
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
    payload = _merge_extra_params(payload, extra_params)
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
    extra_params: dict[str, Any] | None = None,
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
    payload = _merge_extra_params(payload, extra_params)
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


async def stream_openai_responses(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    extra_params: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
    base = _resolve_openai_base(provider)
    if not base:
        raise RuntimeError("Endpoint URL required for OpenAI-compatible provider")
    url = _resolve_openai_responses_url(base)
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": provider.model_type,
        "input": _messages_to_text(messages),
        "temperature": temperature,
    }
    payload = _merge_extra_params(payload, extra_params, protected_keys={"model", "input"})
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    text = _extract_openai_responses_text(data)
    if text:
        yield text, data.get("usage")
    else:
        yield "", data.get("usage")


async def stream_gemini_chat(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    extra_params: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
    url = _resolve_gemini_url(provider.endpoint_url, provider.model_type)
    headers = {
        "x-goog-api-key": provider.api_key,
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {"contents": _messages_to_gemini_contents(messages)}
    if temperature is not None:
        payload["generationConfig"] = {"temperature": temperature}
    payload = _merge_extra_params(payload, extra_params, protected_keys={"contents"})
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    text = _extract_gemini_text(data)
    usage = _extract_gemini_usage(data)
    if text:
        yield text, usage
    else:
        yield "", usage


async def stream_chat(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    extra_params: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[str | None, dict[str, Any] | None]]:
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _ANTHROPIC_NAMES:
        async for chunk, usage in stream_anthropic_chat(
            provider,
            messages,
            temperature=temperature,
            extra_params=extra_params,
        ):
            yield chunk, usage
        return
    if normalized in {"gemini", "google"}:
        async for chunk, usage in stream_gemini_chat(
            provider,
            messages,
            temperature=temperature,
            extra_params=extra_params,
        ):
            yield chunk, usage
        return
    if normalized == "openai" and _should_use_openai_responses(extra_params):
        async for chunk, usage in stream_openai_responses(
            provider,
            messages,
            temperature=temperature,
            extra_params=extra_params,
        ):
            yield chunk, usage
        return
    async for chunk, usage in stream_openai_chat(
        provider,
        messages,
        temperature=temperature,
        extra_params=extra_params,
    ):
        yield chunk, usage


async def collect_chat_completion(
    provider: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    on_chunk: Callable[[str], None] | None = None,
    extra_params: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any] | None]:
    content_parts: list[str] = []
    usage: dict[str, Any] | None = None
    async for chunk, usage_update in stream_chat(
        provider,
        messages,
        temperature=temperature,
        extra_params=extra_params,
    ):
        if chunk:
            content_parts.append(chunk)
            if on_chunk:
                on_chunk(chunk)
        if usage_update:
            usage = usage_update
    return "".join(content_parts).strip(), usage
