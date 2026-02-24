from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import random
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.runtime.tool_context import current_request_id
from shared.observability import REQUEST_ID_HEADER

# ---- Shared httpx client with connection pooling ----
_client: httpx.AsyncClient | None = None
_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 0.2
logger = logging.getLogger(__name__)


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=10,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _client


async def close_client() -> None:
    """Call on app shutdown to close the shared httpx client."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


class ProviderConfig(BaseModel):
    id: int
    provider_name: str
    model_type: str
    api_key: str
    endpoint_url: str | None = None
    encrypted_config: dict | None = None
    prefer: bool = False
    is_valid: bool | None = None


class ProviderFeatureFlags(BaseModel):
    id: int
    user_id: int
    provider_id: int
    model: str
    native_web_search_enabled: bool = False
    image_generation_enabled: bool = False
    audio_enabled: bool = False
    tool_use_enabled: bool = False
    browser_enabled: bool = False
    extra_params_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class SkillEntry(BaseModel):
    skill_id: str
    name: str
    description: str
    source: str
    domains: list[str] = Field(default_factory=list)
    trigger_keywords: list[str] = Field(default_factory=list)
    trigger_extensions: list[str] = Field(default_factory=list)
    enabled_by_default: bool = False
    enabled: bool = False
    user_owned: bool = False
    storage_path: str | None = None
    trust_state: str = "trusted"
    security_scan_status: str = "not_scanned"
    security_warnings: list[str] = Field(default_factory=list)
    provenance: dict | None = None
    last_scanned_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    id: int
    user_id: int
    project_id: str
    task_id: str
    role: str
    content: str
    message_type: str
    metadata: dict | None = None
    created_at: datetime


class ThreadSummary(BaseModel):
    id: int
    project_id: str
    summary: str
    created_at: datetime
    updated_at: datetime


class TaskSummary(BaseModel):
    id: int
    project_id: str | None = None
    task_id: str
    summary: str
    created_at: datetime
    updated_at: datetime


class MemoryNote(BaseModel):
    id: int
    project_id: str
    task_id: str | None = None
    category: str
    content: str
    pinned: bool
    confidence: float = 1.0
    provenance: dict | None = None
    auto_generated: bool = False
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


def _build_headers(auth_header: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if auth_header:
        headers["Authorization"] = auth_header
    if settings.core_api_internal_key:
        headers["X-Internal-Key"] = settings.core_api_internal_key
    request_id = current_request_id.get(None)
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    return headers


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False


async def _request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response:
    client = _get_client()
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_payload,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exc = exc
            if attempt >= _MAX_RETRIES or not _is_retryable_error(exc):
                raise
            sleep_s = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.1)
            logger.warning(
                "core_api_retry",
                extra={
                    "method": method,
                    "url": url,
                    "attempt": attempt,
                    "sleep_s": round(sleep_s, 3),
                    "error": repr(exc),
                },
            )
            await asyncio.sleep(sleep_s)
    if last_exc:
        raise last_exc
    raise RuntimeError("core_api_request_failed_without_exception")


async def fetch_provider(
    auth_header: str | None,
    provider_id: int | None,
    model_provider: str | None,
    model_type: str | None,
) -> ProviderConfig | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    try:
        if provider_id is not None:
            resp = await _request_with_retry(
                "GET",
                f"{base_url}/provider/internal/{provider_id}",
                headers=headers,
            )
            return ProviderConfig(**resp.json())
        resp = await _request_with_retry("GET", f"{base_url}/providers/internal", headers=headers)
        providers = [ProviderConfig(**item) for item in resp.json()]
    except httpx.HTTPError:
        return None

    filtered = providers
    if model_provider:
        needle = model_provider.strip().lower()
        filtered = [item for item in filtered if item.provider_name.lower() == needle]
    if model_type:
        filtered = [item for item in filtered if item.model_type == model_type]
    if not filtered:
        filtered = providers
    preferred = [item for item in filtered if item.prefer]
    return (preferred or filtered or [None])[0]


async def fetch_provider_features(
    auth_header: str | None,
    provider_id: int | None,
    model: str | None,
) -> ProviderFeatureFlags | None:
    if not auth_header or provider_id is None or not model:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    params = {"provider_id": provider_id, "model": model}
    try:
        resp = await _request_with_retry(
            "GET",
            f"{base_url}/provider-features",
            headers=headers,
            params=params,
        )
        payload = resp.json()
        if not payload:
            return None
        return ProviderFeatureFlags(**payload[0])
    except httpx.HTTPError:
        return None


async def fetch_skills(auth_header: str | None) -> list[SkillEntry] | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    try:
        resp = await _request_with_retry("GET", f"{base_url}/skills", headers=headers)
        return [SkillEntry(**item) for item in resp.json()]
    except httpx.HTTPError:
        return None


async def create_history(auth_header: str | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    try:
        resp = await _request_with_retry(
            "POST",
            f"{base_url}/chat/history",
            headers=headers,
            json_payload=payload,
        )
        return resp.json()
    except httpx.HTTPError:
        return None


async def create_message(auth_header: str | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    try:
        resp = await _request_with_retry(
            "POST",
            f"{base_url}/chat/messages",
            headers=headers,
            json_payload=payload,
        )
        return resp.json()
    except httpx.HTTPError:
        return None


async def fetch_messages(
    auth_header: str | None,
    project_id: str | None,
    task_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[ChatMessage]:
    if not auth_header:
        return []
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return []
    headers = _build_headers(auth_header)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if project_id:
        params["project_id"] = project_id
    if task_id:
        params["task_id"] = task_id
    try:
        resp = await _request_with_retry(
            "GET",
            f"{base_url}/chat/messages",
            headers=headers,
            params=params,
        )
        return [ChatMessage(**item) for item in resp.json()]
    except httpx.HTTPError:
        return []


async def fetch_configs(
    auth_header: str | None,
    group: str | None = None,
) -> list[dict[str, Any]]:
    if not auth_header:
        return []
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return []
    headers = _build_headers(auth_header)
    params = {"group": group} if group else None
    try:
        resp = await _request_with_retry(
            "GET",
            f"{base_url}/configs",
            headers=headers,
            params=params,
        )
        return resp.json()
    except httpx.HTTPError:
        return []


async def fetch_mcp_users(auth_header: str | None) -> list[dict[str, Any]]:
    if not auth_header:
        return []
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return []
    headers = _build_headers(auth_header)
    try:
        resp = await _request_with_retry("GET", f"{base_url}/mcp/users", headers=headers)
        return resp.json()
    except httpx.HTTPError:
        return []


async def search_chat_messages(
    auth_header: str | None,
    query: str,
    project_id: str | None = None,
    task_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if not auth_header:
        return []
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return []
    headers = _build_headers(auth_header)
    params: dict[str, Any] = {"query": query, "limit": limit}
    if project_id:
        params["project_id"] = project_id
    if task_id:
        params["task_id"] = task_id
    try:
        resp = await _request_with_retry(
            "GET",
            f"{base_url}/memory/search",
            headers=headers,
            params=params,
        )
        return resp.json()
    except httpx.HTTPError:
        return []


async def fetch_memory_notes(
    auth_header: str | None,
    project_id: str,
    task_id: str | None = None,
) -> list[MemoryNote]:
    if not auth_header:
        return []
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return []
    headers = _build_headers(auth_header)
    params: dict[str, Any] = {"project_id": project_id}
    if task_id:
        params["task_id"] = task_id
    try:
        resp = await _request_with_retry(
            "GET",
            f"{base_url}/memory/notes",
            headers=headers,
            params=params,
        )
        return [MemoryNote(**item) for item in resp.json()]
    except httpx.HTTPError:
        return []


async def create_memory_note(
    auth_header: str | None,
    payload: dict[str, Any],
) -> MemoryNote | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    try:
        resp = await _request_with_retry(
            "POST",
            f"{base_url}/memory/notes",
            headers=headers,
            json_payload=payload,
        )
        return MemoryNote(**resp.json())
    except httpx.HTTPError:
        return None


async def fetch_thread_summary(
    auth_header: str | None,
    project_id: str,
) -> ThreadSummary | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    params = {"project_id": project_id}
    try:
        resp = await _request_with_retry(
            "GET",
            f"{base_url}/memory/thread-summary",
            headers=headers,
            params=params,
        )
        return ThreadSummary(**resp.json())
    except httpx.HTTPError:
        return None


async def upsert_thread_summary(
    auth_header: str | None,
    project_id: str,
    summary: str,
) -> ThreadSummary | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    payload = {"project_id": project_id, "summary": summary}
    try:
        resp = await _request_with_retry(
            "PUT",
            f"{base_url}/memory/thread-summary",
            headers=headers,
            json_payload=payload,
        )
        return ThreadSummary(**resp.json())
    except httpx.HTTPError:
        return None


async def fetch_task_summary(
    auth_header: str | None,
    task_id: str,
) -> TaskSummary | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    params = {"task_id": task_id}
    try:
        resp = await _request_with_retry(
            "GET",
            f"{base_url}/memory/task-summary",
            headers=headers,
            params=params,
        )
        return TaskSummary(**resp.json())
    except httpx.HTTPError:
        return None


async def upsert_task_summary(
    auth_header: str | None,
    task_id: str,
    summary: str,
    project_id: str | None = None,
) -> TaskSummary | None:
    if not auth_header:
        return None
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return None
    headers = _build_headers(auth_header)
    payload = {"task_id": task_id, "project_id": project_id, "summary": summary}
    try:
        resp = await _request_with_retry(
            "PUT",
            f"{base_url}/memory/task-summary",
            headers=headers,
            json_payload=payload,
        )
        return TaskSummary(**resp.json())
    except httpx.HTTPError:
        return None


async def update_history(
    auth_header: str | None,
    history_id: int,
    payload: dict[str, Any],
) -> None:
    if not auth_header:
        return
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return
    headers = _build_headers(auth_header)
    try:
        await _request_with_retry(
            "PUT",
            f"{base_url}/chat/history/{history_id}",
            headers=headers,
            json_payload=payload,
        )
    except httpx.HTTPError:
        return
