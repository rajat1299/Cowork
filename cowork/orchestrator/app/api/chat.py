import asyncio
import json
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.runtime.events import StepEvent
from shared.schemas import StepEvent as StepEventModel

router = APIRouter(tags=["chat"])


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


@router.post("/chat")
async def start_chat(request: ChatRequest):
    async def event_stream():
        now = time.time()
        yield format_sse(
            StepEventModel(
                task_id=request.task_id,
                step=StepEvent.confirmed,
                data={"question": request.question},
                timestamp=now,
            )
        )
        await asyncio.sleep(0.1)
        yield format_sse(
            StepEventModel(
                task_id=request.task_id,
                step=StepEvent.end,
                data={"result": "stub response"},
                timestamp=time.time(),
            )
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
