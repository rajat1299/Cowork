from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import ChatHistory

router = APIRouter(prefix="/chat", tags=["history"])


class ChatHistoryCreate(BaseModel):
    task_id: str
    project_id: str | None = None
    question: str
    language: str = "en"
    model_platform: str = ""
    model_type: str = ""
    api_key: str | None = None
    api_url: str | None = None
    max_retries: int = 3
    file_save_path: str | None = None
    installed_mcp: dict | None = None
    project_name: str | None = None
    summary: str | None = None
    tokens: int = 0
    spend: float = 0.0
    status: int = 1


class ChatHistoryUpdate(BaseModel):
    project_name: str | None = None
    summary: str | None = None
    tokens: int | None = None
    spend: float | None = None
    status: int | None = None
    project_id: str | None = None


class ChatHistoryOut(BaseModel):
    id: int
    task_id: str
    project_id: str | None
    question: str
    language: str
    model_platform: str
    model_type: str
    api_key: str | None
    api_url: str | None
    max_retries: int
    file_save_path: str | None
    installed_mcp: dict | None
    project_name: str | None
    summary: str | None
    tokens: int
    spend: float
    status: int
    created_at: datetime
    updated_at: datetime


class ProjectGroupOut(BaseModel):
    project_id: str
    project_name: str | None = None
    total_tokens: int
    task_count: int
    latest_task_date: datetime
    last_prompt: str
    tasks: list[ChatHistoryOut]
    total_completed_tasks: int
    total_ongoing_tasks: int


class GroupedHistoryOut(BaseModel):
    projects: list[ProjectGroupOut]
    total_projects: int
    total_tasks: int
    total_tokens: int


@router.post("/history", response_model=ChatHistoryOut)
def create_history(
    request: ChatHistoryCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatHistoryOut:
    project_id = request.project_id or request.task_id
    record = ChatHistory(
        user_id=user.id,
        task_id=request.task_id,
        project_id=project_id,
        question=request.question,
        language=request.language,
        model_platform=request.model_platform,
        model_type=request.model_type,
        api_key=request.api_key,
        api_url=request.api_url,
        max_retries=request.max_retries,
        file_save_path=request.file_save_path,
        installed_mcp=request.installed_mcp,
        project_name=request.project_name,
        summary=request.summary,
        tokens=request.tokens,
        spend=request.spend,
        status=request.status,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return ChatHistoryOut(**record.__dict__)


@router.get("/history", response_model=ChatHistoryOut)
def get_history(
    task_id: str = Query(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatHistoryOut:
    record = session.exec(
        select(ChatHistory).where(ChatHistory.task_id == task_id, ChatHistory.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="History not found")
    return ChatHistoryOut(**record.__dict__)


@router.get("/history/{history_id}", response_model=ChatHistoryOut)
def get_history_by_id(
    history_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatHistoryOut:
    record = session.exec(
        select(ChatHistory).where(ChatHistory.id == history_id, ChatHistory.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="History not found")
    return ChatHistoryOut(**record.__dict__)


@router.get("/histories", response_model=list[ChatHistoryOut])
def list_histories(
    project_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ChatHistoryOut]:
    statement = select(ChatHistory).where(ChatHistory.user_id == user.id)
    if project_id:
        statement = statement.where(ChatHistory.project_id == project_id)
    statement = statement.order_by(ChatHistory.created_at.desc()).offset(offset).limit(limit)
    records = session.exec(statement).all()
    return [ChatHistoryOut(**record.__dict__) for record in records]


@router.get("/histories/grouped", response_model=GroupedHistoryOut)
def list_grouped_histories(
    include_tasks: bool = Query(default=True),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> GroupedHistoryOut:
    statement = (
        select(ChatHistory)
        .where(ChatHistory.user_id == user.id)
        .order_by(ChatHistory.created_at.desc())
    )
    records = session.exec(statement).all()

    grouped: dict[str, dict] = {}
    total_tokens = 0
    for record in records:
        project_id = record.project_id or record.task_id
        total_tokens += record.tokens

        if project_id not in grouped:
            grouped[project_id] = {
                "project_id": project_id,
                "project_name": record.project_name,
                "total_tokens": 0,
                "task_count": 0,
                "latest_task_date": record.created_at,
                "last_prompt": record.question,
                "tasks": [],
                "total_completed_tasks": 0,
                "total_ongoing_tasks": 0,
            }
        item = grouped[project_id]
        item["total_tokens"] += record.tokens
        item["task_count"] += 1

        if record.created_at >= item["latest_task_date"]:
            item["latest_task_date"] = record.created_at
            item["last_prompt"] = record.question
            if record.project_name:
                item["project_name"] = record.project_name
        elif not item["project_name"] and record.project_name:
            item["project_name"] = record.project_name

        if record.status == 2:
            item["total_completed_tasks"] += 1
        else:
            item["total_ongoing_tasks"] += 1

        if include_tasks:
            item["tasks"].append(ChatHistoryOut(**record.__dict__))

    projects = [ProjectGroupOut(**item) for item in grouped.values()]
    projects.sort(key=lambda item: item.latest_task_date, reverse=True)

    return GroupedHistoryOut(
        projects=projects,
        total_projects=len(projects),
        total_tasks=len(records),
        total_tokens=total_tokens,
    )


@router.put("/history/{history_id}", response_model=ChatHistoryOut)
def update_history(
    history_id: int,
    request: ChatHistoryUpdate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ChatHistoryOut:
    record = session.exec(
        select(ChatHistory).where(ChatHistory.id == history_id, ChatHistory.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="History not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    session.refresh(record)
    return ChatHistoryOut(**record.__dict__)


@router.delete("/history/{history_id}")
def delete_history(
    history_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = session.exec(
        select(ChatHistory).where(ChatHistory.id == history_id, ChatHistory.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="History not found")
    session.delete(record)
    session.commit()
    return Response(status_code=204)
