from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.storage import add_step, list_steps
from shared.schemas import StepEvent

router = APIRouter(prefix="/chat", tags=["chat"])


class StepOut(BaseModel):
    id: int
    task_id: str
    step: str
    data: dict
    timestamp: float | None
    created_at: datetime


@router.post("/steps", response_model=StepOut)
def create_step(event: StepEvent) -> StepOut:
    record = add_step(event.task_id, event.step, event.data, event.timestamp)
    return StepOut(**record.__dict__)


@router.get("/steps", response_model=list[StepOut])
def get_steps(task_id: str | None = Query(default=None)) -> list[StepOut]:
    return [StepOut(**record.__dict__) for record in list_steps(task_id)]
