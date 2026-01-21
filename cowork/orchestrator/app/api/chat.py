import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.runtime.actions import ActionImprove, ActionStop, TaskStatus
from app.runtime.engine import run_task_loop
from app.runtime.manager import get, get_or_create, remove
from shared.schemas import StepEvent as StepEventModel
from shared.ratelimit import SlidingWindowLimiter, ip_key, rate_limit

router = APIRouter(tags=["chat"])
_chat_limiter = SlidingWindowLimiter(
    max_requests=settings.rate_limit_chat_per_minute,
    window_seconds=60,
)
_chat_rate_limit = rate_limit(_chat_limiter, ip_key("chat"))


class ChatRequest(BaseModel):
    project_id: str
    task_id: str
    question: str


def format_sse(event: StepEventModel) -> str:
    payload = {
        "task_id": event.task_id,
        "step": event.step,
        "data": event.data,
        "timestamp": event.timestamp,
    }
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat", dependencies=[Depends(_chat_rate_limit)])
async def start_chat(request: ChatRequest):
    async def event_stream():
        task_lock = get_or_create(request.project_id)
        await task_lock.put(
            ActionImprove(
                project_id=request.project_id,
                task_id=request.task_id,
                question=request.question,
            )
        )
        try:
            async for event in run_task_loop(task_lock):
                yield format_sse(event)
        finally:
            if task_lock.status in {TaskStatus.done, TaskStatus.stopped}:
                remove(request.project_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class ImproveRequest(BaseModel):
    task_id: str
    question: str


@router.post("/chat/{project_id}/improve", dependencies=[Depends(_chat_rate_limit)])
async def improve_chat(project_id: str, request: ImproveRequest):
    task_lock = get(project_id)
    if not task_lock:
        raise HTTPException(status_code=404, detail="Project not found")
    await task_lock.put(
        ActionImprove(
            project_id=project_id,
            task_id=request.task_id,
            question=request.question,
        )
    )
    return {"status": "queued"}


@router.delete("/chat/{project_id}", dependencies=[Depends(_chat_rate_limit)])
async def stop_chat(project_id: str):
    task_lock = get(project_id)
    if not task_lock:
        raise HTTPException(status_code=404, detail="Project not found")
    await task_lock.put(ActionStop(project_id=project_id, reason="user_stop"))
    return {"status": "stopping"}
