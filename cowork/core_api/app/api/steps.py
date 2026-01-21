from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.internal_auth import require_internal_key
from app.models import ChatHistory, Step
from shared.schemas import StepEvent

router = APIRouter(prefix="/chat", tags=["chat"])


class StepOut(BaseModel):
    id: int
    task_id: str
    step: str
    data: dict
    timestamp: float | None
    created_at: datetime


@router.post("/steps", response_model=StepOut, dependencies=[Depends(require_internal_key)])
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
    task_id: str = Query(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[StepOut]:
    history = session.exec(
        select(ChatHistory).where(ChatHistory.task_id == task_id, ChatHistory.user_id == user.id)
    ).first()
    if not history:
        raise HTTPException(status_code=404, detail="History not found")
    statement = select(Step).where(Step.task_id == task_id).order_by(Step.id.asc())
    records = session.exec(statement).all()
    return [StepOut(**record.__dict__) for record in records]
