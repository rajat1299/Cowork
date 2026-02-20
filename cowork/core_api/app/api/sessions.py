from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import Session as SessionModel

router = APIRouter(tags=["sessions"])


class SessionCreate(BaseModel):
    project_id: str
    title: str | None = None
    first_message: str | None = None


class SessionUpdate(BaseModel):
    title: str


class SessionOut(BaseModel):
    id: int
    project_id: str
    title: str
    created_at: datetime
    updated_at: datetime


def _generate_title(first_message: str | None, fallback: str) -> str:
    if first_message:
        return (first_message.strip()[:60] or fallback).strip()
    return fallback


@router.post("/sessions", response_model=SessionOut)
def create_session(
    request: SessionCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if request.project_id == "GLOBAL_USER_CONTEXT":
        raise HTTPException(status_code=400, detail="Reserved project id")
    existing = session.exec(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.project_id == request.project_id,
        )
    ).first()
    if existing:
        return SessionOut(**existing.__dict__)
    title = request.title or _generate_title(request.first_message, f"Session {request.project_id}")
    record = SessionModel(
        user_id=user.id,
        project_id=request.project_id,
        title=title,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return SessionOut(**record.__dict__)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    records = session.exec(
        select(SessionModel).where(SessionModel.user_id == user.id).order_by(SessionModel.updated_at.desc())
    ).all()
    return [SessionOut(**record.__dict__) for record in records]


@router.put("/sessions/{session_id}", response_model=SessionOut)
def update_session(
    session_id: int,
    request: SessionUpdate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = session.exec(
        select(SessionModel).where(SessionModel.id == session_id, SessionModel.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    record.title = request.title
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    session.refresh(record)
    return SessionOut(**record.__dict__)
