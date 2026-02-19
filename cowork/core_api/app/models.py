from datetime import date as dt_date, datetime
from typing import Optional

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RefreshToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    token: str = Field(index=True, unique=True)
    expires_at: datetime
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Config(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    group: str = Field(index=True)
    name: str = Field(index=True)
    value: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SearchUsage(SQLModel, table=True):
    __tablename__ = "search_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "date", name="uq_search_usage_user_provider_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    provider: str = Field(index=True)
    date: dt_date = Field(index=True)
    requests_count: int = Field(default=0)
    results_count: int = Field(default=0)
    cost_usd_estimate: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Step(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    step: str = Field(index=True)
    data: dict = Field(sa_column=Column(JSONB))
    timestamp: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Artifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    artifact_type: str = Field(index=True)
    name: str
    content_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Session(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    project_id: str = Field(index=True, unique=True)
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OAuthAccount(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    provider: str = Field(index=True)
    provider_user_id: str = Field(index=True)
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Provider(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    provider_name: str = Field(index=True)
    model_type: str
    api_key: str
    endpoint_url: str = ""
    encrypted_config: dict | None = Field(default=None, sa_column=Column(JSONB))
    prefer: bool = Field(default=False)
    is_valid: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProviderFeatureFlags(SQLModel, table=True):
    __tablename__ = "provider_feature_flags"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider_id",
            "model",
            name="uq_provider_feature_flags_user_provider_model",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    provider_id: int = Field(index=True, foreign_key="provider.id")
    model: str = Field(index=True)
    native_web_search_enabled: bool = Field(default=False)
    image_generation_enabled: bool = Field(default=False)
    audio_enabled: bool = Field(default=False)
    tool_use_enabled: bool = Field(default=False)
    browser_enabled: bool = Field(default=False)
    extra_params_json: dict | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Skill(SQLModel, table=True):
    __tablename__ = "skill"
    __table_args__ = (UniqueConstraint("skill_id", name="uq_skill_skill_id"),)

    id: int | None = Field(default=None, primary_key=True)
    skill_id: str = Field(index=True)
    name: str
    description: str = ""
    source: str = Field(default="built_in", index=True)
    domains: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    trigger_keywords: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    trigger_extensions: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    owner_user_id: int | None = Field(default=None, foreign_key="user.id")
    storage_path: str | None = None
    enabled_by_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserSkillState(SQLModel, table=True):
    __tablename__ = "user_skill_state"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_skill_state_user_skill"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    skill_id: str = Field(index=True)
    enabled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    task_id: str = Field(index=True, unique=True)
    project_id: str | None = Field(default=None, index=True)
    question: str
    language: str
    model_platform: str
    model_type: str
    api_key: str | None = None
    api_url: str | None = None
    max_retries: int = Field(default=3)
    file_save_path: str | None = None
    installed_mcp: dict | None = Field(default=None, sa_column=Column(JSONB))
    project_name: str | None = None
    summary: str | None = None
    tokens: int = Field(default=0)
    spend: float = Field(default=0.0)
    status: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    project_id: str = Field(index=True)
    task_id: str = Field(index=True)
    role: str = Field(index=True)
    content: str
    message_type: str = Field(default="message")
    meta: dict | None = Field(default=None, sa_column=Column("metadata", JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ThreadSummary(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    project_id: str = Field(index=True)
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TaskSummary(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    project_id: str | None = Field(default=None, index=True)
    task_id: str = Field(index=True)
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryNote(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    project_id: str = Field(index=True)
    task_id: str | None = Field(default=None, index=True)
    category: str = Field(default="note", index=True)
    content: str
    pinned: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSnapshot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    task_id: str = Field(index=True)
    browser_url: str
    image_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class McpServer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    key: str = Field(index=True, unique=True)
    description: str = ""
    home_page: str | None = None
    mcp_type: str = Field(default="local")
    status: str = Field(default="online")
    install_command: dict | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class McpUser(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    mcp_id: int | None = Field(default=None, foreign_key="mcpserver.id")
    user_id: int = Field(index=True, foreign_key="user.id")
    mcp_name: str
    mcp_key: str
    mcp_desc: str | None = None
    command: str | None = None
    args: list[str] | None = Field(default=None, sa_column=Column(JSONB))
    env: dict | None = Field(default=None, sa_column=Column(JSONB))
    mcp_type: str = Field(default="local")
    status: str = Field(default="enable")
    server_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
