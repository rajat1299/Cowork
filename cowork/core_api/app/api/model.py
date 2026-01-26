from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["model"])


class ValidateModelRequest(BaseModel):
    model_platform: str = Field(..., description="Model platform/provider")
    model_type: str = Field(..., description="Model type")
    api_key: str = Field(..., description="API key")
    url: str | None = Field(None, description="Custom endpoint URL")
    extra_params: dict | None = Field(None, description="Extra model parameters")


class ValidateModelResponse(BaseModel):
    is_valid: bool
    is_tool_calls: bool | None = None
    message: str | None = None
    error: str | None = None


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


def _normalize_provider_name(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _resolve_openai_url(endpoint_url: str) -> str:
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


def _merge_extra_params(payload: dict[str, Any], extra_params: dict | None) -> None:
    if not extra_params:
        return
    for key, value in extra_params.items():
        if key in payload:
            continue
        payload[key] = value


def _openai_tool_payload(model_type: str, extra_params: dict | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_type,
        "messages": [
            {
                "role": "user",
                "content": "Call validate_tool with an empty JSON object.",
            }
        ],
        "temperature": 0,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "validate_tool",
                    "description": "Validation tool for testing tool calls.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "validate_tool"}},
    }
    _merge_extra_params(payload, extra_params)
    return payload


def _openai_plain_payload(model_type: str, extra_params: dict | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_type,
        "messages": [{"role": "user", "content": "Reply with the word ok."}],
        "temperature": 0,
    }
    _merge_extra_params(payload, extra_params)
    return payload


def _anthropic_tool_payload(model_type: str, extra_params: dict | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_type,
        "max_tokens": 64,
        "temperature": 0,
        "messages": [{"role": "user", "content": "Call validate_tool with an empty JSON object."}],
        "tools": [
            {
                "name": "validate_tool",
                "description": "Validation tool for testing tool calls.",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
        "tool_choice": {"type": "tool", "name": "validate_tool"},
    }
    _merge_extra_params(payload, extra_params)
    return payload


def _anthropic_plain_payload(model_type: str, extra_params: dict | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_type,
        "max_tokens": 64,
        "temperature": 0,
        "messages": [{"role": "user", "content": "Reply with the word ok."}],
    }
    _merge_extra_params(payload, extra_params)
    return payload


def _extract_openai_tool_calls(payload: dict[str, Any]) -> bool:
    choices = payload.get("choices") or []
    if not choices:
        return False
    message = choices[0].get("message") or {}
    if message.get("tool_calls"):
        return True
    if message.get("function_call"):
        return True
    return False


def _extract_anthropic_tool_calls(payload: dict[str, Any]) -> bool:
    content = payload.get("content") or []
    for block in content:
        if block.get("type") == "tool_use":
            return True
    return False


async def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def _validate_openai_compat(request: ValidateModelRequest, base_url: str) -> ValidateModelResponse:
    url = _resolve_openai_url(base_url)
    headers = {
        "Authorization": f"Bearer {request.api_key}",
        "Content-Type": "application/json",
    }
    try:
        payload = _openai_tool_payload(request.model_type, request.extra_params)
        data = await _post_json(url, headers, payload)
        is_tool_calls = _extract_openai_tool_calls(data)
        if is_tool_calls:
            return ValidateModelResponse(
                is_valid=True,
                is_tool_calls=True,
                message="Validation succeeded.",
            )
        return ValidateModelResponse(
            is_valid=True,
            is_tool_calls=False,
            message="Model responded but did not return tool calls.",
        )
    except Exception as exc:
        logger.warning("Model validation tool-call attempt failed: %s", exc)
        try:
            payload = _openai_plain_payload(request.model_type, request.extra_params)
            data = await _post_json(url, headers, payload)
            is_valid = bool(data.get("choices"))
            return ValidateModelResponse(
                is_valid=is_valid,
                is_tool_calls=False,
                message="Model responded but tool calls were not verified.",
                error=None if is_valid else "No response choices returned.",
            )
        except Exception as fallback_exc:
            return ValidateModelResponse(
                is_valid=False,
                is_tool_calls=False,
                message="Validation failed.",
                error=str(fallback_exc),
            )


async def _validate_anthropic(request: ValidateModelRequest) -> ValidateModelResponse:
    url = _resolve_anthropic_url(request.url)
    headers = {
        "x-api-key": request.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    try:
        payload = _anthropic_tool_payload(request.model_type, request.extra_params)
        data = await _post_json(url, headers, payload)
        is_tool_calls = _extract_anthropic_tool_calls(data)
        if is_tool_calls:
            return ValidateModelResponse(
                is_valid=True,
                is_tool_calls=True,
                message="Validation succeeded.",
            )
        return ValidateModelResponse(
            is_valid=True,
            is_tool_calls=False,
            message="Model responded but did not return tool calls.",
        )
    except Exception as exc:
        logger.warning("Anthropic tool-call validation failed: %s", exc)
        try:
            payload = _anthropic_plain_payload(request.model_type, request.extra_params)
            data = await _post_json(url, headers, payload)
            is_valid = bool(data.get("content"))
            return ValidateModelResponse(
                is_valid=is_valid,
                is_tool_calls=False,
                message="Model responded but tool calls were not verified.",
                error=None if is_valid else "No response content returned.",
            )
        except Exception as fallback_exc:
            return ValidateModelResponse(
                is_valid=False,
                is_tool_calls=False,
                message="Validation failed.",
                error=str(fallback_exc),
            )


@router.post("/model/validate", response_model=ValidateModelResponse)
async def validate_model(request: ValidateModelRequest, user=Depends(get_current_user)):
    if not request.api_key or not request.api_key.strip():
        return ValidateModelResponse(
            is_valid=False,
            is_tool_calls=False,
            message="Invalid API key.",
            error="invalid_api_key",
        )

    normalized = _normalize_provider_name(request.model_platform)
    if normalized in _ANTHROPIC_NAMES:
        return await _validate_anthropic(request)

    base_url = request.url or _OPENAI_COMPAT_DEFAULTS.get(normalized)
    if not base_url:
        if normalized in _OPENAI_COMPAT_REQUIRES_ENDPOINT:
            return ValidateModelResponse(
                is_valid=False,
                is_tool_calls=False,
                message="Endpoint URL required for OpenAI-compatible provider.",
                error="missing_endpoint_url",
            )
        base_url = "https://api.openai.com/v1"
    return await _validate_openai_compat(request, base_url)
