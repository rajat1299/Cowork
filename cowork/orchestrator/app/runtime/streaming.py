from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable

from app.runtime.artifacts import _collect_tool_artifacts
from app.runtime.events import StepEvent
from app.runtime.memory import _usage_total
from app.runtime.sync import fire_and_forget
from app.runtime.tool_context import current_project_id
from app.runtime.tracing import _trace_step
from shared.schemas import AgentEvent, StepEvent as StepEventModel


logger = logging.getLogger(__name__)


def _emit(task_id: str, step: StepEvent, data: dict) -> StepEventModel:
    artifact_payloads: list[dict[str, Any]] = []
    if step == StepEvent.deactivate_toolkit:
        artifact_payloads = _collect_tool_artifacts(task_id, data)
    _trace_step(task_id, step, data)
    payload = _attach_agent_event(task_id, step, data)
    event = StepEventModel(
        task_id=task_id,
        step=step,
        data=payload,
        timestamp=time.time(),
    )
    fire_and_forget(event)
    for artifact_payload in artifact_payloads:
        _emit(task_id, StepEvent.artifact, artifact_payload)
    return event


def _attach_agent_event(task_id: str, step: StepEvent, data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    if "agent_event" in data:
        return data
    agent_event = _build_agent_event(task_id, step, data)
    if agent_event is None:
        return data
    return {**data, "agent_event": agent_event}


def _build_agent_event(task_id: str, step: StepEvent, data: dict) -> dict | None:
    event_type = _map_step_to_agent_event(step)
    if event_type is None:
        return None
    payload = _agent_event_payload(step, data)
    timestamp_ms = int(time.time() * 1000)
    session_id = data.get("project_id") or current_project_id.get(None)
    event = AgentEvent(
        type=event_type,
        payload=payload,
        timestamp_ms=timestamp_ms,
        turn_id=task_id,
        session_id=session_id,
    )
    return event.model_dump(exclude_none=True)


def _map_step_to_agent_event(step: StepEvent) -> str | None:
    if step == StepEvent.confirmed:
        return "message_start"
    if step == StepEvent.streaming:
        return "text_delta"
    if step == StepEvent.decompose_text:
        return "text_delta"
    if step == StepEvent.end:
        return "message_end"
    if step == StepEvent.activate_toolkit:
        return "tool_exec_start"
    if step == StepEvent.deactivate_toolkit:
        return "tool_exec_end"
    if step == StepEvent.error:
        return "error"
    if step == StepEvent.notice:
        return "notice"
    if step == StepEvent.ask_user:
        return "ask_user"
    if step == StepEvent.turn_cancelled:
        return "turn_cancelled"
    if step in {
        StepEvent.context_too_long,
        StepEvent.to_sub_tasks,
        StepEvent.assign_task,
        StepEvent.task_state,
        StepEvent.create_agent,
        StepEvent.activate_agent,
        StepEvent.deactivate_agent,
    }:
        return "state_boundary"
    return None


def _agent_event_payload(step: StepEvent, data: dict) -> dict:
    if step == StepEvent.streaming:
        return {"text": data.get("chunk", "")}
    if step == StepEvent.decompose_text:
        return {"text": data.get("content", ""), "channel": "decompose"}
    if step == StepEvent.confirmed:
        return {"question": data.get("question")}
    if step == StepEvent.activate_toolkit:
        return {
            "toolkit": data.get("toolkit_name"),
            "method": data.get("method_name"),
            "agent_name": data.get("agent_name"),
            "process_task_id": data.get("process_task_id"),
            "args": data.get("message"),
        }
    if step == StepEvent.deactivate_toolkit:
        return {
            "toolkit": data.get("toolkit_name"),
            "method": data.get("method_name"),
            "agent_name": data.get("agent_name"),
            "process_task_id": data.get("process_task_id"),
            "result": data.get("message"),
        }
    if step == StepEvent.error:
        return {"message": data.get("error") or data.get("message")}
    if step == StepEvent.ask_user:
        return data
    if step == StepEvent.turn_cancelled:
        return {"reason": data.get("reason")}
    if step == StepEvent.end:
        return data
    return {"kind": step.value, "data": data}


@dataclass
class TokenTracker:
    total_tokens: int = 0

    def add(self, usage: dict | None) -> int:
        tokens = _usage_total(usage)
        self.total_tokens += tokens
        return tokens


class EventStream:
    def __init__(
        self,
        task_id: str,
        loop: asyncio.AbstractEventLoop,
        step_listener: Callable[[StepEvent, dict[str, Any]], None] | None = None,
    ) -> None:
        self.task_id = task_id
        self.loop = loop
        self.queue: asyncio.Queue[StepEventModel | None] = asyncio.Queue()
        self._step_listener = step_listener

    def emit(self, step: StepEvent, data: dict) -> None:
        artifact_payloads: list[dict[str, Any]] = []
        if step == StepEvent.deactivate_toolkit:
            artifact_payloads = _collect_tool_artifacts(self.task_id, data)
        event = _emit(self.task_id, step, data)
        events: list[tuple[StepEvent, dict[str, Any], StepEventModel]] = [(step, data, event)]
        for artifact_payload in artifact_payloads:
            artifact_event = _emit(self.task_id, StepEvent.artifact, artifact_payload)
            events.append((StepEvent.artifact, artifact_payload, artifact_event))

        def _enqueue() -> None:
            for queued_step, queued_data, queued_event in events:
                if self._step_listener is not None:
                    try:
                        self._step_listener(queued_step, queued_data)
                    except Exception as exc:
                        logger.warning("step_listener_failed: %s", exc)
                self.queue.put_nowait(queued_event)

        if self.loop.is_running():
            self.loop.call_soon_threadsafe(_enqueue)
        else:
            _enqueue()

    def close(self) -> None:
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
        else:
            self.queue.put_nowait(None)

    async def stream(self) -> AsyncIterator[StepEventModel]:
        while True:
            event = await self.queue.get()
            if event is None:
                break
            yield event
