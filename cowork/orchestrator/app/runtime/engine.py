import asyncio
import time
from typing import AsyncIterator

from app.runtime.actions import ActionType, TaskStatus
from app.runtime.task_lock import TaskLock
from app.runtime.events import StepEvent
from app.runtime.sync import fire_and_forget
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
            await asyncio.sleep(0.1)
            end_event = StepEventModel(
                task_id=action.task_id,
                step=StepEvent.end,
                data={"result": "stub response"},
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
