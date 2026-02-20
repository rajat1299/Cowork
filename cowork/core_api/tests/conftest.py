from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import User
from app.security import create_access_token, hash_password


# SQLite does not support PostgreSQL's JSONB type natively. For tests we map it
# to JSON so metadata can be created in an in-memory database.
@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_type, _compiler, **_kwargs) -> str:
    return "JSON"


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def client(test_engine):
    def _override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def test_user(db_session: Session) -> User:
    user = User(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("TestPassw0rd!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    return create_access_token(test_user.id)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}
