from __future__ import annotations

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
    prefer: bool = False


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
