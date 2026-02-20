from __future__ import annotations

import httpx
from fastapi import Cookie, Header, HTTPException

from app.config import settings


def _normalize_bearer_header(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    return f"Bearer {token}"


def _auth_headers(authorization: str) -> dict[str, str]:
    headers = {"Authorization": authorization}
    if settings.core_api_internal_key:
        headers["X-Internal-Key"] = settings.core_api_internal_key
    return headers


async def _verify_with_core_api(authorization: str) -> None:
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/auth/me", headers=_auth_headers(authorization))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc

    if response.status_code == 200:
        return
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=401, detail="Invalid access token")
    raise HTTPException(status_code=503, detail="Authentication service unavailable")


async def require_auth(
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
) -> str:
    if authorization:
        normalized = _normalize_bearer_header(authorization)
    else:
        cookie_token = access_token.strip() if access_token else ""
        if not cookie_token:
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        normalized = f"Bearer {cookie_token}"
    await _verify_with_core_api(normalized)
    return normalized
