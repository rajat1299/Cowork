import asyncio

import httpx

from app.config import settings
from shared.schemas import StepEvent


async def send_step(event: StepEvent) -> None:
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return
    url = f"{base_url}/chat/steps"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json=event.model_dump())
    except Exception:
        return


def fire_and_forget(event: StepEvent) -> None:
    asyncio.create_task(send_step(event))
