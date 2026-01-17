from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.auth import get_current_user
from app.config_catalog import is_valid_env_var, list_catalog
from app.storage import create_config, delete_config, list_configs, update_config

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
):
    return [ConfigOut(**cfg.__dict__) for cfg in list_configs(user.id, group)]


@router.post("/configs", response_model=ConfigOut)
def create_config_entry(
    request: ConfigCreate,
    user=Depends(get_current_user),
):
    if not is_valid_env_var(request.group, request.name):
        raise HTTPException(status_code=400, detail="Invalid config group or name")
    record = create_config(user.id, request.group, request.name, request.value)
    return ConfigOut(**record.__dict__)


@router.put("/configs/{config_id}", response_model=ConfigOut)
def update_config_entry(
    config_id: int,
    request: ConfigCreate,
    user=Depends(get_current_user),
):
    if not is_valid_env_var(request.group, request.name):
        raise HTTPException(status_code=400, detail="Invalid config group or name")
    try:
        record = update_config(config_id, user.id, request.group, request.name, request.value)
    except KeyError:
        raise HTTPException(status_code=404, detail="Config not found")
    return ConfigOut(**record.__dict__)


@router.delete("/configs/{config_id}")
def delete_config_entry(config_id: int, user=Depends(get_current_user)):
    try:
        delete_config(config_id, user.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Config not found")
    return Response(status_code=204)
