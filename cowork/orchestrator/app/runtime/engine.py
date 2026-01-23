import asyncio
import time
from typing import AsyncIterator

from app.clients.core_api import ProviderConfig, create_history, fetch_provider, update_history
from app.runtime.actions import ActionType, TaskStatus
from app.runtime.events import StepEvent
from app.runtime.llm_client import stream_openai_chat
from app.runtime.sync import fire_and_forget
from app.runtime.task_lock import TaskLock
from shared.schemas import StepEvent as StepEventModel


async def run_task_loop(task_lock: TaskLock) -> AsyncIterator[StepEventModel]:
    while True:
        try:
            action = await task_lock.get()
        except asyncio.CancelledError:
            break

        if action.type == ActionType.improve:
            task_lock.status = TaskStatus.processing
            task_lock.current_task_id = action.task_id
            confirm_event = StepEventModel(
                task_id=action.task_id,
                step=StepEvent.confirmed,
                data={"question": action.question},
                timestamp=time.time(),
            )
            fire_and_forget(confirm_event)
            yield confirm_event
            state_event = StepEventModel(
                task_id=action.task_id,
                step=StepEvent.task_state,
                data={"state": "processing"},
                timestamp=time.time(),
            )
            fire_and_forget(state_event)
            yield state_event

            provider: ProviderConfig | None = None
            if action.api_key and action.model_type:
                provider = ProviderConfig(
                    id=0,
                    provider_name=action.model_provider or "custom",
                    model_type=action.model_type,
                    api_key=action.api_key,
                    endpoint_url=action.endpoint_url,
                    prefer=True,
                )
            if not provider:
                provider = await fetch_provider(
                    action.auth_token,
                    action.provider_id,
                    action.model_provider,
                    action.model_type,
                )

            if not provider or not provider.api_key or not provider.model_type:
                error_event = StepEventModel(
                    task_id=action.task_id,
                    step=StepEvent.error,
                    data={"error": "No provider configured"},
                    timestamp=time.time(),
                )
                fire_and_forget(error_event)
                yield error_event
                end_event = StepEventModel(
                    task_id=action.task_id,
                    step=StepEvent.end,
                    data={"result": "error", "reason": "No provider configured"},
                    timestamp=time.time(),
                )
                fire_and_forget(end_event)
                yield end_event
                task_lock.status = TaskStatus.done
                continue

            history_id = None
            history_payload = {
                "task_id": action.task_id,
                "project_id": action.project_id,
                "question": action.question,
                "language": "en",
                "model_platform": provider.provider_name,
                "model_type": provider.model_type,
                "status": 1,
            }
            history = await create_history(action.auth_token, history_payload)
            if history:
                history_id = history.get("id")

            content_parts: list[str] = []
            usage: dict | None = None
            try:
                messages = [{"role": "user", "content": action.question}]
                async for chunk, usage_update in stream_openai_chat(provider, messages):
                    if chunk:
                        content_parts.append(chunk)
                        stream_event = StepEventModel(
                            task_id=action.task_id,
                            step=StepEvent.streaming,
                            data={"chunk": chunk},
                            timestamp=time.time(),
                        )
                        fire_and_forget(stream_event)
                        yield stream_event
                    if usage_update:
                        usage = usage_update
            except Exception as exc:
                error_event = StepEventModel(
                    task_id=action.task_id,
                    step=StepEvent.error,
                    data={"error": str(exc)},
                    timestamp=time.time(),
                )
                fire_and_forget(error_event)
                yield error_event
                end_event = StepEventModel(
                    task_id=action.task_id,
                    step=StepEvent.end,
                    data={"result": "error", "reason": "Model call failed"},
                    timestamp=time.time(),
                )
                fire_and_forget(end_event)
                yield end_event
                if history_id is not None:
                    await update_history(action.auth_token, history_id, {"status": 3})
                task_lock.status = TaskStatus.done
                continue

            result_text = "".join(content_parts).strip()
            total_tokens = 0
            if usage:
                total_tokens = int(usage.get("total_tokens") or 0)
            if history_id is not None:
                await update_history(action.auth_token, history_id, {"tokens": total_tokens, "status": 2})

            end_event = StepEventModel(
                task_id=action.task_id,
                step=StepEvent.end,
                data={"result": result_text, "usage": usage or {}},
                timestamp=time.time(),
            )
            fire_and_forget(end_event)
            yield end_event
            task_lock.status = TaskStatus.done
            continue

        if action.type == ActionType.stop:
            task_lock.status = TaskStatus.stopped
            stop_event = StepEventModel(
                task_id=task_lock.current_task_id or "unknown",
                step=StepEvent.end,
                data={"result": "stopped", "reason": action.reason},
                timestamp=time.time(),
            )
            fire_and_forget(stop_event)
            yield stop_event
            break
