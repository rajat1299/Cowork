from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import ChatSnapshot
from app.storage import resolve_snapshot_path, save_snapshot_image

router = APIRouter(prefix="/chat", tags=["snapshots"])


class ChatSnapshotCreate(BaseModel):
    task_id: str
    browser_url: str
    image_base64: str


class ChatSnapshotOut(BaseModel):
    id: int
    task_id: str
    browser_url: str
    image_path: str
    created_at: datetime
    image_url: str


def _snapshot_out(record: ChatSnapshot) -> ChatSnapshotOut:
    return ChatSnapshotOut(
        id=record.id,
        task_id=record.task_id,
        browser_url=record.browser_url,
        image_path=record.image_path,
        created_at=record.created_at,
        image_url=f"/chat/snapshots/{record.id}/file",
    )


@router.post("/snapshots", response_model=ChatSnapshotOut)
def create_snapshot(
    request: ChatSnapshotCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatSnapshotOut:
    image_path = save_snapshot_image(user.id, request.task_id, request.image_base64)
    record = ChatSnapshot(
        user_id=user.id,
        task_id=request.task_id,
        browser_url=request.browser_url,
        image_path=image_path,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _snapshot_out(record)


@router.get("/snapshots", response_model=list[ChatSnapshotOut])
def list_snapshots(
    task_id: str | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ChatSnapshotOut]:
    statement = select(ChatSnapshot).where(ChatSnapshot.user_id == user.id)
    if task_id:
        statement = statement.where(ChatSnapshot.task_id == task_id)
    records = session.exec(statement).all()
    return [_snapshot_out(record) for record in records]


@router.get("/snapshots/{snapshot_id}", response_model=ChatSnapshotOut)
def get_snapshot(
    snapshot_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatSnapshotOut:
    record = session.exec(
        select(ChatSnapshot).where(ChatSnapshot.id == snapshot_id, ChatSnapshot.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return _snapshot_out(record)


@router.get("/snapshots/{snapshot_id}/file")
def get_snapshot_file(
    snapshot_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> FileResponse:
    record = session.exec(
        select(ChatSnapshot).where(ChatSnapshot.id == snapshot_id, ChatSnapshot.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    try:
        file_path = resolve_snapshot_path(record.image_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snapshot path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file missing")
    return FileResponse(file_path)


@router.delete("/snapshots/{snapshot_id}")
def delete_snapshot(
    snapshot_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = session.exec(
        select(ChatSnapshot).where(ChatSnapshot.id == snapshot_id, ChatSnapshot.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    try:
        file_path = resolve_snapshot_path(record.image_path)
        if file_path.exists():
            file_path.unlink()
    except ValueError:
        pass
    session.delete(record)
    session.commit()
    return Response(status_code=204)
