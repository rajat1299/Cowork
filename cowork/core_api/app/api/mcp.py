from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, HttpUrl
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import McpServer, McpUser

router = APIRouter(tags=["mcp"])


McpType = Literal["local", "remote"]
McpStatus = Literal["online", "offline"]
McpUserStatus = Literal["enable", "disable"]


class McpServerCreate(BaseModel):
    name: str
    key: str
    description: str = ""
    home_page: HttpUrl | None = None
    mcp_type: McpType = "local"
    status: McpStatus = "online"
    install_command: dict | None = None


class McpServerOut(BaseModel):
    id: int
    name: str
    key: str
    description: str
    home_page: str | None
    mcp_type: McpType
    status: McpStatus
    install_command: dict | None
    created_at: datetime
    updated_at: datetime


class McpInstallRequest(BaseModel):
    mcp_id: int


class McpUserOut(BaseModel):
    id: int
    mcp_id: int | None
    mcp_name: str
    mcp_key: str
    mcp_desc: str | None
    command: str | None
    args: list[str] | None
    env: dict | None
    mcp_type: McpType
    status: McpUserStatus
    server_url: str | None
    created_at: datetime
    updated_at: datetime


class McpUserUpdate(BaseModel):
    mcp_name: str | None = None
    mcp_desc: str | None = None
    status: McpUserStatus | None = None
    mcp_type: McpType | None = None
    env: dict | None = None
    server_url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    mcp_key: str | None = None


class McpImportLocal(BaseModel):
    mcpServers: dict[str, dict]


class McpImportRemote(BaseModel):
    server_name: str
    server_url: HttpUrl


def _validate_local_import(mcp_servers: dict[str, dict]) -> None:
    if not mcp_servers:
        raise HTTPException(status_code=400, detail="mcpServers is required")
    for name, config in mcp_servers.items():
        if not name:
            raise HTTPException(status_code=400, detail="MCP server name is required")
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail=f"Invalid config for {name}")
        command = config.get("command")
        if not isinstance(command, str) or not command:
            raise HTTPException(status_code=400, detail=f"Invalid command for {name}")
        args = config.get("args")
        if args is not None:
            if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
                raise HTTPException(status_code=400, detail=f"Invalid args for {name}")
        env = config.get("env")
        if env is not None and not isinstance(env, dict):
            raise HTTPException(status_code=400, detail=f"Invalid env for {name}")


@router.get("/mcps", response_model=list[McpServerOut])
def list_mcps(
    keyword: str | None = Query(default=None),
    mine: bool | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[McpServerOut]:
    statement = select(McpServer)
    if keyword:
        statement = statement.where(McpServer.key.ilike(f"%{keyword}%"))
    if mine:
        user_mcps = session.exec(
            select(McpUser.mcp_id).where(McpUser.user_id == user.id, McpUser.mcp_id.is_not(None))
        ).all()
        ids = [mcp_id for mcp_id in user_mcps if mcp_id is not None]
        if ids:
            statement = statement.where(McpServer.id.in_(ids))
        else:
            return []
    records = session.exec(statement).all()
    return [McpServerOut(**record.__dict__) for record in records]


@router.get("/mcp/{mcp_id}", response_model=McpServerOut)
def get_mcp(
    mcp_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> McpServerOut:
    record = session.exec(select(McpServer).where(McpServer.id == mcp_id)).first()
    if not record:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return McpServerOut(**record.__dict__)


@router.post("/mcp", response_model=McpServerOut)
def create_mcp(
    request: McpServerCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> McpServerOut:
    record = McpServer(
        name=request.name,
        key=request.key,
        description=request.description,
        home_page=str(request.home_page) if request.home_page else None,
        mcp_type=request.mcp_type,
        status=request.status,
        install_command=request.install_command,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return McpServerOut(**record.__dict__)


@router.post("/mcp/install", response_model=McpUserOut)
def install_mcp(
    request: McpInstallRequest,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> McpUserOut:
    mcp = session.exec(select(McpServer).where(McpServer.id == request.mcp_id)).first()
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP server not found")
    existing = session.exec(
        select(McpUser).where(McpUser.user_id == user.id, McpUser.mcp_id == mcp.id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="MCP already installed")
    install_command = mcp.install_command or {}
    record = McpUser(
        mcp_id=mcp.id,
        user_id=user.id,
        mcp_name=mcp.name,
        mcp_key=mcp.key,
        mcp_desc=mcp.description,
        command=install_command.get("command"),
        args=install_command.get("args"),
        env=install_command.get("env"),
        mcp_type=mcp.mcp_type,
        status="enable",
        server_url=None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return McpUserOut(**record.__dict__)


@router.post("/mcp/import/{mcp_type}")
def import_mcp(
    mcp_type: str,
    payload: dict,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if mcp_type == "local":
        data = McpImportLocal(**payload)
        _validate_local_import(data.mcpServers)
        count = 0
        for name, config in data.mcpServers.items():
            record = McpUser(
                mcp_id=None,
                user_id=user.id,
                mcp_name=name,
                mcp_key=name,
                mcp_desc=config.get("description") or name,
                command=config.get("command"),
                args=config.get("args"),
                env=config.get("env"),
                mcp_type="local",
                status="enable",
                server_url=None,
            )
            session.add(record)
            count += 1
        session.commit()
        return {"message": "Local MCP servers imported", "count": count}
    if mcp_type == "remote":
        data = McpImportRemote(**payload)
        record = McpUser(
            mcp_id=None,
            user_id=user.id,
            mcp_name=data.server_name,
            mcp_key=data.server_name,
            mcp_desc=None,
            command=None,
            args=None,
            env=None,
            mcp_type="remote",
            status="enable",
            server_url=str(data.server_url),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return McpUserOut(**record.__dict__)
    raise HTTPException(status_code=400, detail="Unsupported MCP import type")


@router.get("/mcp/users", response_model=list[McpUserOut])
def list_mcp_users(
    mcp_id: int | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[McpUserOut]:
    statement = select(McpUser).where(McpUser.user_id == user.id)
    if mcp_id is not None:
        statement = statement.where(McpUser.mcp_id == mcp_id)
    records = session.exec(statement).all()
    return [McpUserOut(**record.__dict__) for record in records]


@router.get("/mcp/users/{mcp_user_id}", response_model=McpUserOut)
def get_mcp_user(
    mcp_user_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> McpUserOut:
    record = session.exec(
        select(McpUser).where(McpUser.id == mcp_user_id, McpUser.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="MCP user not found")
    return McpUserOut(**record.__dict__)


@router.put("/mcp/users/{mcp_user_id}", response_model=McpUserOut)
def update_mcp_user(
    mcp_user_id: int,
    request: McpUserUpdate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> McpUserOut:
    record = session.exec(
        select(McpUser).where(McpUser.id == mcp_user_id, McpUser.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="MCP user not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)
    return McpUserOut(**record.__dict__)


@router.delete("/mcp/users/{mcp_user_id}")
def delete_mcp_user(
    mcp_user_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = session.exec(
        select(McpUser).where(McpUser.id == mcp_user_id, McpUser.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="MCP user not found")
    session.delete(record)
    session.commit()
    return Response(status_code=204)
