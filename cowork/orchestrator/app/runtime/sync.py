import asyncio
import logging
import random
import threading

import httpx

from app.config import settings
from shared.observability import REQUEST_ID_HEADER
from shared.schemas import ArtifactEvent, StepEvent

logger = logging.getLogger(__name__)
_sync_client: httpx.AsyncClient | None = None
_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 0.2


def _build_headers() -> dict[str, str]:
    if settings.core_api_internal_key:
        return {"X-Internal-Key": settings.core_api_internal_key}
    return {}


def _get_client() -> httpx.AsyncClient:
    global _sync_client
    if _sync_client is None or _sync_client.is_closed:
        _sync_client = httpx.AsyncClient(
            timeout=5,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )
    return _sync_client


async def close_client() -> None:
    global _sync_client
    if _sync_client is not None and not _sync_client.is_closed:
        await _sync_client.aclose()
        _sync_client = None


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return False


async def _post_with_retry(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str],
    log_name: str,
) -> None:
    client = _get_client()
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return
        except Exception as exc:
            if attempt >= _MAX_RETRIES or not _is_retryable(exc):
                logger.warning(
                    "%s_failed",
                    log_name,
                    extra={"url": url, "attempt": attempt, "error": repr(exc)},
                )
                raise
            sleep_s = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 0.1)
            logger.info(
                "%s_retry",
                log_name,
                extra={"url": url, "attempt": attempt, "sleep_s": round(sleep_s, 3)},
            )
            await asyncio.sleep(sleep_s)


async def send_step(event: StepEvent) -> None:
    base_url = settings.core_api_url.rstrip("/")
    if not base_url:
        return
    url = f"{base_url}/chat/steps"
    try:
        headers = _build_headers()
        if event.request_id:
            headers[REQUEST_ID_HEADER] = event.request_id
        await _post_with_retry(
            url,
            event.model_dump(),
            headers=headers,
            log_name="send_step",
        )
    except Exception as exc:
        logger.warning("send_step_drop", extra={"url": url, "error": repr(exc)})


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
        if event.request_id:
            headers[REQUEST_ID_HEADER] = event.request_id
        await _post_with_retry(
            url,
            event.model_dump(),
            headers=headers,
            log_name="send_artifact",
        )
    except Exception as exc:
        logger.warning("send_artifact_drop", extra={"url": url, "error": repr(exc)})


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
