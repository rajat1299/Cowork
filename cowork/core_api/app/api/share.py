from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import ChatHistory
from app.share import create_share_token, decode_share_token

router = APIRouter(prefix="/chat", tags=["share"])


class ShareCreate(BaseModel):
    task_id: str


class ShareTokenOut(BaseModel):
    token: str
    expires_at: str


class ShareInfoOut(BaseModel):
    question: str
    language: str
    model_platform: str
    model_type: str
    max_retries: int
    project_name: str | None = None
    summary: str | None = None


@router.post("/share", response_model=ShareTokenOut)
def create_share_link(
    request: ShareCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ShareTokenOut:
    history = session.exec(
        select(ChatHistory).where(ChatHistory.task_id == request.task_id, ChatHistory.user_id == user.id)
    ).first()
    if not history:
        raise HTTPException(status_code=404, detail="History not found")
    token, expires_at = create_share_token(request.task_id)
    return ShareTokenOut(token=token, expires_at=expires_at.isoformat())


@router.get("/share/info/{token}", response_model=ShareInfoOut)
def get_share_info(token: str, session: Session = Depends(get_session)) -> ShareInfoOut:
    try:
        task_id = decode_share_token(token)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid share token")
    history = session.exec(select(ChatHistory).where(ChatHistory.task_id == task_id)).first()
    if not history:
        raise HTTPException(status_code=404, detail="Share not found")
    return ShareInfoOut(
        question=history.question,
        language=history.language,
        model_platform=history.model_platform,
        model_type=history.model_type,
        max_retries=history.max_retries,
        project_name=history.project_name,
        summary=history.summary,
    )
