import asyncio
import logging
import threading

import httpx

from app.config import settings
from shared.schemas import ArtifactEvent, StepEvent

logger = logging.getLogger(__name__)


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


def _run_coro_in_thread(coro) -> None:
    """Run a coroutine in a new thread with its own event loop."""
    def thread_target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(coro)
            finally:
                loop.close()
        except Exception as e:
            logger.warning(f"Failed to run coroutine in thread: {e}")

    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()


def fire_and_forget(event: StepEvent) -> None:
    """Safely fire and forget an async step event from any context.
    
    Handles both async and sync contexts by:
    1. If running in an async context, schedules the coroutine as a task
    2. If no event loop is running, spawns a thread with its own loop
    """
    coro = send_step(event)
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, create a task
        task = loop.create_task(coro)
        # Add done callback to log any exceptions
        def handle_exception(t):
            try:
                t.result()
            except Exception as e:
                logger.warning(f"fire_and_forget task failed: {e}")
        task.add_done_callback(handle_exception)
    except RuntimeError:
        # No running event loop - run in a separate thread
        _run_coro_in_thread(coro)


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
    """Safely fire and forget an async artifact event from any context."""
    coro = send_artifact(event)
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(coro)
        def handle_exception(t):
            try:
                t.result()
            except Exception as e:
                logger.warning(f"fire_and_forget_artifact task failed: {e}")
        task.add_done_callback(handle_exception)
    except RuntimeError:
        _run_coro_in_thread(coro)
