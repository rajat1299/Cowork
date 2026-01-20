from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config_catalog import is_valid_env_var, list_catalog
from app.db import get_session
from app.models import Config

router = APIRouter(tags=["config"])


class ConfigCreate(BaseModel):
    group: str
    name: str
    value: str


class ConfigOut(BaseModel):
    id: int
    group: str
    name: str
    value: str
    created_at: datetime
    updated_at: datetime


@router.get("/config/info")
def config_info():
    return list_catalog()


@router.get("/configs", response_model=list[ConfigOut])
def get_configs(
    group: str | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    statement = select(Config).where(Config.user_id == user.id)
    if group:
        statement = statement.where(Config.group == group)
    records = session.exec(statement).all()
    return [ConfigOut(**record.__dict__) for record in records]


@router.post("/configs", response_model=ConfigOut)
def create_config_entry(
    request: ConfigCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not is_valid_env_var(request.group, request.name):
        raise HTTPException(status_code=400, detail="Invalid config group or name")
    record = Config(
        user_id=user.id,
        group=request.group,
        name=request.name,
        value=request.value,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return ConfigOut(**record.__dict__)


@router.put("/configs/{config_id}", response_model=ConfigOut)
def update_config_entry(
    config_id: int,
    request: ConfigCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not is_valid_env_var(request.group, request.name):
        raise HTTPException(status_code=400, detail="Invalid config group or name")
    record = session.exec(
        select(Config).where(Config.id == config_id, Config.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    record.group = request.group
    record.name = request.name
    record.value = request.value
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)
    return ConfigOut(**record.__dict__)


@router.delete("/configs/{config_id}")
def delete_config_entry(
    config_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = session.exec(
        select(Config).where(Config.id == config_id, Config.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    session.delete(record)
    session.commit()
    return Response(status_code=204)
