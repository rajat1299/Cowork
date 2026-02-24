from datetime import datetime
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.internal_auth import require_internal_key
from app.models import Artifact, ChatHistory
from shared.schemas import ArtifactEvent

router = APIRouter(prefix="/chat", tags=["artifacts"])
_idempotency_lock = threading.Lock()
_idempotency_to_artifact_id: dict[str, int] = {}


class ArtifactOut(BaseModel):
    id: int
    task_id: str
    artifact_type: str
    name: str
    content_url: str | None
    created_at: datetime


@router.post("/artifacts", response_model=ArtifactOut, dependencies=[Depends(require_internal_key)])
def create_artifact(event: ArtifactEvent, session: Session = Depends(get_session)) -> ArtifactOut:
    idem_key = event.idempotency_key or ""
    if idem_key:
        with _idempotency_lock:
            existing_id = _idempotency_to_artifact_id.get(idem_key)
        if existing_id is not None:
            existing = session.exec(select(Artifact).where(Artifact.id == existing_id)).first()
            if existing:
                return ArtifactOut(**existing.__dict__)

    record = Artifact(
        task_id=event.task_id,
        artifact_type=event.artifact_type,
        name=event.name,
        content_url=event.content_url,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    if idem_key:
        with _idempotency_lock:
            _idempotency_to_artifact_id[idem_key] = int(record.id)
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
