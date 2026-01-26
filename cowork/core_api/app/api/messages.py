from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.internal_auth import require_internal_key
from app.models import ChatMessage

router = APIRouter(prefix="/chat", tags=["messages"])


class MessageCreate(BaseModel):
    project_id: str
    task_id: str
    role: str
    content: str
    message_type: str = Field(default="message")
    metadata: dict | None = None


class MessageOut(BaseModel):
    id: int
    user_id: int
    project_id: str
    task_id: str
    role: str
    content: str
    message_type: str
    metadata: dict | None
    created_at: datetime


@router.post("/messages", response_model=MessageOut, dependencies=[Depends(require_internal_key)])
def create_message(
    request: MessageCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MessageOut:
    record = ChatMessage(
        user_id=user.id,
        project_id=request.project_id,
        task_id=request.task_id,
        role=request.role,
        content=request.content,
        message_type=request.message_type or "message",
        meta=request.metadata,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return MessageOut(**record.__dict__, metadata=record.meta)


@router.get("/messages", response_model=list[MessageOut])
def list_messages(
    project_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[MessageOut]:
    if not project_id and not task_id:
        raise HTTPException(status_code=400, detail="project_id or task_id is required")
    statement = select(ChatMessage).where(ChatMessage.user_id == user.id)
    if project_id:
        statement = statement.where(ChatMessage.project_id == project_id)
    if task_id:
        statement = statement.where(ChatMessage.task_id == task_id)
    statement = statement.order_by(ChatMessage.id.asc()).offset(offset).limit(limit)
    records = session.exec(statement).all()
    return [MessageOut(**record.__dict__, metadata=record.meta) for record in records]
