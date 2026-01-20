from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import Artifact
from shared.schemas import ArtifactEvent

router = APIRouter(prefix="/chat", tags=["artifacts"])


class ArtifactOut(BaseModel):
    id: int
    task_id: str
    artifact_type: str
    name: str
    content_url: str | None
    created_at: datetime


@router.post("/artifacts", response_model=ArtifactOut)
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
    task_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[ArtifactOut]:
    statement = select(Artifact)
    if task_id:
        statement = statement.where(Artifact.task_id == task_id)
    records = session.exec(statement).all()
    return [ArtifactOut(**record.__dict__) for record in records]
