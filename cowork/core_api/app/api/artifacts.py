from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.internal_auth import require_internal_key
from app.models import Artifact, ChatHistory
from shared.schemas import ArtifactEvent

router = APIRouter(prefix="/chat", tags=["artifacts"])


class ArtifactOut(BaseModel):
    id: int
    task_id: str
    artifact_type: str
    name: str
    content_url: str | None
    created_at: datetime


@router.post("/artifacts", response_model=ArtifactOut, dependencies=[Depends(require_internal_key)])
def create_artifact(event: ArtifactEvent, session: Session = Depends(get_session)) -> ArtifactOut:
    record = Artifact(
        task_id=event.task_id,
        artifact_type=event.artifact_type,
        name=event.name,
        content_url=event.content_url,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return ArtifactOut(**record.__dict__)


@router.get("/artifacts", response_model=list[ArtifactOut])
def get_artifacts(
    task_id: str = Query(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ArtifactOut]:
    history = session.exec(
        select(ChatHistory).where(ChatHistory.task_id == task_id, ChatHistory.user_id == user.id)
    ).first()
    if not history:
        raise HTTPException(status_code=404, detail="History not found")
    statement = select(Artifact).where(Artifact.task_id == task_id).order_by(Artifact.id.asc())
    records = session.exec(statement).all()
    return [ArtifactOut(**record.__dict__) for record in records]
