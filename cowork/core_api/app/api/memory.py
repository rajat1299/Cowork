from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import ChatMessage, MemoryNote, TaskSummary, ThreadSummary

router = APIRouter(prefix="/memory", tags=["memory"])


class ThreadSummaryCreate(BaseModel):
    project_id: str
    summary: str


class ThreadSummaryOut(BaseModel):
    id: int
    project_id: str
    summary: str
    created_at: datetime
    updated_at: datetime


class TaskSummaryCreate(BaseModel):
    task_id: str
    project_id: str | None = None
    summary: str


class TaskSummaryOut(BaseModel):
    id: int
    task_id: str
    project_id: str | None
    summary: str
    created_at: datetime
    updated_at: datetime


class MemoryNoteCreate(BaseModel):
    project_id: str
    task_id: str | None = None
    category: str = "note"
    content: str
    pinned: bool = False


class MemoryNoteUpdate(BaseModel):
    category: str | None = None
    content: str | None = None
    pinned: bool | None = None


class MemoryNoteOut(BaseModel):
    id: int
    project_id: str
    task_id: str | None
    category: str
    content: str
    pinned: bool
    created_at: datetime
    updated_at: datetime


class ContextStatsOut(BaseModel):
    project_id: str
    task_id: str | None
    last_updated_at: datetime | None
    thread_summary_updated_at: datetime | None
    task_summary_updated_at: datetime | None
    notes_updated_at: datetime | None
    note_count: int
    pinned_count: int


class ChatSearchResultOut(BaseModel):
    id: int
    project_id: str
    task_id: str
    role: str
    content: str
    message_type: str
    created_at: datetime
    rank: float


class ClearMemoryRequest(BaseModel):
    project_id: str


@router.get("/thread-summary", response_model=ThreadSummaryOut)
def get_thread_summary(
    project_id: str = Query(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ThreadSummaryOut:
    record = session.exec(
        select(ThreadSummary).where(
            ThreadSummary.user_id == user.id,
            ThreadSummary.project_id == project_id,
        )
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Thread summary not found")
    return ThreadSummaryOut(**record.__dict__)


@router.put("/thread-summary", response_model=ThreadSummaryOut)
def upsert_thread_summary(
    request: ThreadSummaryCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ThreadSummaryOut:
    record = session.exec(
        select(ThreadSummary).where(
            ThreadSummary.user_id == user.id,
            ThreadSummary.project_id == request.project_id,
        )
    ).first()
    if record:
        record.summary = request.summary
        record.updated_at = datetime.utcnow()
    else:
        record = ThreadSummary(
            user_id=user.id,
            project_id=request.project_id,
            summary=request.summary,
        )
    session.add(record)
    session.commit()
    session.refresh(record)
    return ThreadSummaryOut(**record.__dict__)


@router.get("/task-summary", response_model=TaskSummaryOut)
def get_task_summary(
    task_id: str = Query(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TaskSummaryOut:
    record = session.exec(
        select(TaskSummary).where(
            TaskSummary.user_id == user.id,
            TaskSummary.task_id == task_id,
        )
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Task summary not found")
    return TaskSummaryOut(**record.__dict__)


@router.put("/task-summary", response_model=TaskSummaryOut)
def upsert_task_summary(
    request: TaskSummaryCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TaskSummaryOut:
    record = session.exec(
        select(TaskSummary).where(
            TaskSummary.user_id == user.id,
            TaskSummary.task_id == request.task_id,
        )
    ).first()
    if record:
        record.summary = request.summary
        record.project_id = request.project_id or record.project_id
        record.updated_at = datetime.utcnow()
    else:
        record = TaskSummary(
            user_id=user.id,
            project_id=request.project_id,
            task_id=request.task_id,
            summary=request.summary,
        )
    session.add(record)
    session.commit()
    session.refresh(record)
    return TaskSummaryOut(**record.__dict__)


@router.get("/notes", response_model=list[MemoryNoteOut])
def list_memory_notes(
    project_id: str = Query(...),
    task_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[MemoryNoteOut]:
    statement = select(MemoryNote).where(
        MemoryNote.user_id == user.id,
        MemoryNote.project_id == project_id,
    )
    if task_id:
        statement = statement.where(MemoryNote.task_id == task_id)
    if category:
        statement = statement.where(MemoryNote.category == category)
    statement = statement.order_by(MemoryNote.created_at.asc())
    records = session.exec(statement).all()
    return [MemoryNoteOut(**record.__dict__) for record in records]


@router.post("/notes", response_model=MemoryNoteOut)
def create_memory_note(
    request: MemoryNoteCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MemoryNoteOut:
    record = MemoryNote(
        user_id=user.id,
        project_id=request.project_id,
        task_id=request.task_id,
        category=request.category,
        content=request.content,
        pinned=request.pinned,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return MemoryNoteOut(**record.__dict__)


@router.put("/notes/{note_id}", response_model=MemoryNoteOut)
def update_memory_note(
    note_id: int,
    request: MemoryNoteUpdate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MemoryNoteOut:
    record = session.exec(
        select(MemoryNote).where(
            MemoryNote.id == note_id,
            MemoryNote.user_id == user.id,
        )
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Memory note not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)
    return MemoryNoteOut(**record.__dict__)


@router.delete("/notes/{note_id}")
def delete_memory_note(
    note_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = session.exec(
        select(MemoryNote).where(
            MemoryNote.id == note_id,
            MemoryNote.user_id == user.id,
        )
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Memory note not found")
    session.delete(record)
    session.commit()
    return Response(status_code=204)


@router.get("/context-stats", response_model=ContextStatsOut)
def get_context_stats(
    project_id: str = Query(...),
    task_id: str | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ContextStatsOut:
    thread_summary = session.exec(
        select(ThreadSummary).where(
            ThreadSummary.user_id == user.id,
            ThreadSummary.project_id == project_id,
        )
    ).first()
    thread_summary_updated = thread_summary.updated_at if thread_summary else None

    note_statement = select(MemoryNote).where(
        MemoryNote.user_id == user.id,
        MemoryNote.project_id == project_id,
    )
    if task_id:
        note_statement = note_statement.where(MemoryNote.task_id == task_id)
    notes = session.exec(note_statement).all()
    notes_updated = max((note.updated_at for note in notes), default=None)
    note_count = len(notes)
    pinned_count = sum(1 for note in notes if note.pinned)

    task_summary_statement = select(TaskSummary).where(
        TaskSummary.user_id == user.id,
        TaskSummary.project_id == project_id,
    )
    if task_id:
        task_summary_statement = task_summary_statement.where(TaskSummary.task_id == task_id)
    task_summaries = session.exec(task_summary_statement).all()
    task_summary_updated = max((summary.updated_at for summary in task_summaries), default=None)

    candidates = [thread_summary_updated, task_summary_updated, notes_updated]
    last_updated = max((item for item in candidates if item is not None), default=None)

    return ContextStatsOut(
        project_id=project_id,
        task_id=task_id,
        last_updated_at=last_updated,
        thread_summary_updated_at=thread_summary_updated,
        task_summary_updated_at=task_summary_updated,
        notes_updated_at=notes_updated,
        note_count=note_count,
        pinned_count=pinned_count,
    )


@router.post("/clear")
def clear_memory(
    request: ClearMemoryRequest,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    summaries = session.exec(
        select(ThreadSummary).where(
            ThreadSummary.user_id == user.id,
            ThreadSummary.project_id == request.project_id,
        )
    ).all()
    for summary in summaries:
        session.delete(summary)

    task_summaries = session.exec(
        select(TaskSummary).where(
            TaskSummary.user_id == user.id,
            TaskSummary.project_id == request.project_id,
        )
    ).all()
    for summary in task_summaries:
        session.delete(summary)

    notes = session.exec(
        select(MemoryNote).where(
            MemoryNote.user_id == user.id,
            MemoryNote.project_id == request.project_id,
        )
    ).all()
    for note in notes:
        session.delete(note)

    session.commit()
    return Response(status_code=204)


@router.get("/search", response_model=list[ChatSearchResultOut])
def search_chat_messages(
    query: str = Query(..., min_length=1),
    project_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ChatSearchResultOut]:
    ts_query = func.plainto_tsquery("english", query)
    tsvector = func.to_tsvector("english", ChatMessage.content)
    rank = func.ts_rank_cd(tsvector, ts_query).label("rank")
    statement = (
        select(ChatMessage, rank)
        .where(ChatMessage.user_id == user.id)
        .where(tsvector.op("@@")(ts_query))
    )
    if project_id:
        statement = statement.where(ChatMessage.project_id == project_id)
    if task_id:
        statement = statement.where(ChatMessage.task_id == task_id)
    statement = statement.order_by(rank.desc(), ChatMessage.created_at.desc()).limit(limit)
    results = session.exec(statement).all()
    payload: list[ChatSearchResultOut] = []
    for record, score in results:
        payload.append(
            ChatSearchResultOut(
                id=record.id,
                project_id=record.project_id,
                task_id=record.task_id,
                role=record.role,
                content=record.content,
                message_type=record.message_type,
                created_at=record.created_at,
                rank=float(score or 0.0),
            )
        )
    return payload
