from datetime import datetime
from typing import Optional

from sqlalchemy import Column
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
