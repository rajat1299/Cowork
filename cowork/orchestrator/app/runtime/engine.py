import asyncio
import time
from typing import AsyncIterator

import app.runtime.toolkits  # register default toolkits
from app.runtime.actions import ActionType, TaskStatus
from app.runtime.events import StepEvent
from app.runtime.sync import fire_and_forget, fire_and_forget_artifact
from app.runtime.task_lock import TaskLock
from app.runtime.toolkits.base import ToolkitCall
from app.runtime.toolkits.registry import get_toolkit
from shared.schemas import ArtifactEvent, StepEvent as StepEventModel


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
            toolkit = get_toolkit("demo")
            if toolkit:
                activate_event = StepEventModel(
                    task_id=action.task_id,
                    step=StepEvent.activate_toolkit,
                    data={"toolkit": toolkit.name, "input": {"question": action.question}},
                    timestamp=time.time(),
                )
                fire_and_forget(activate_event)
                yield activate_event
                result = await toolkit.run(ToolkitCall(name=toolkit.name, input={"question": action.question}))
                deactivate_event = StepEventModel(
                    task_id=action.task_id,
                    step=StepEvent.deactivate_toolkit,
                    data={"toolkit": toolkit.name, "output": result.output},
                    timestamp=time.time(),
                )
                fire_and_forget(deactivate_event)
                yield deactivate_event
                artifact = ArtifactEvent(
                    task_id=action.task_id,
                    artifact_type="text",
                    name="demo-output",
                    content_url=None,
                    created_at=time.time(),
                )
                fire_and_forget_artifact(artifact)
                yield StepEventModel(
                    task_id=action.task_id,
                    step=StepEvent.artifact,
                    data=artifact.model_dump(),
                    timestamp=time.time(),
                )
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
