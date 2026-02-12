from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings


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
    enabled_by_default: bool = False
    enabled: bool = False
    user_owned: bool = False
    storage_path: str | None = None
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
    created_at: datetime
    updated_at: datetime


def _build_headers(auth_header: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if auth_header:
        headers["Authorization"] = auth_header
    if settings.core_api_internal_key:
        headers["X-Internal-Key"] = settings.core_api_internal_key
    return headers


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
        async with httpx.AsyncClient(timeout=10) as client:
            if provider_id is not None:
                resp = await client.get(f"{base_url}/provider/internal/{provider_id}", headers=headers)
                resp.raise_for_status()
                return ProviderConfig(**resp.json())
            resp = await client.get(f"{base_url}/providers/internal", headers=headers)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/provider-features", headers=headers, params=params)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/skills", headers=headers)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{base_url}/chat/history", json=payload, headers=headers)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{base_url}/chat/messages", json=payload, headers=headers)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/chat/messages", headers=headers, params=params)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/configs", headers=headers, params=params)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/mcp/users", headers=headers)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/memory/search", headers=headers, params=params)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/memory/notes", headers=headers, params=params)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{base_url}/memory/notes", json=payload, headers=headers)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/memory/thread-summary", headers=headers, params=params)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(f"{base_url}/memory/thread-summary", headers=headers, json=payload)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/memory/task-summary", headers=headers, params=params)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(f"{base_url}/memory/task-summary", headers=headers, json=payload)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(f"{base_url}/chat/history/{history_id}", json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPError:
        return
