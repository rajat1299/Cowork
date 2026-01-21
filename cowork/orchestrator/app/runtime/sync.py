import asyncio

import httpx

from app.config import settings
from shared.schemas import ArtifactEvent, StepEvent


def _build_headers() -> dict[str, str]:
    if settings.core_api_internal_key:
        return {"X-Internal-Key": settings.core_api_internal_key}
    return {}


async def send_step(event: StepEvent) -> None:
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return
    url = f"{base_url}/chat/steps"
    try:
        headers = _build_headers()
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json=event.model_dump(), headers=headers)
    except Exception:
        return


def fire_and_forget(event: StepEvent) -> None:
    asyncio.create_task(send_step(event))


async def send_artifact(event: ArtifactEvent) -> None:
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return
    url = f"{base_url}/chat/artifacts"
    try:
        headers = _build_headers()
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json=event.model_dump(), headers=headers)
    except Exception:
        return


def fire_and_forget_artifact(event: ArtifactEvent) -> None:
    asyncio.create_task(send_artifact(event))
