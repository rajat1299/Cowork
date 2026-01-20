from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import Step
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
def create_step(event: StepEvent, session: Session = Depends(get_session)) -> StepOut:
    record = Step(
        task_id=event.task_id,
        step=event.step,
        data=event.data,
        timestamp=event.timestamp,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return StepOut(**record.__dict__)


@router.get("/steps", response_model=list[StepOut])
def get_steps(
    task_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[StepOut]:
    statement = select(Step)
    if task_id:
        statement = statement.where(Step.task_id == task_id)
    records = session.exec(statement).all()
    return [StepOut(**record.__dict__) for record in records]
