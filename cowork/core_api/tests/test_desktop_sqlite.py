from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlmodel import create_engine
from sqlalchemy import text

from app.config import CoreApiSettings
from app.db import ensure_sqlite_schema_compatibility


def test_desktop_env_defaults_database_url_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "desktop")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)

    settings = CoreApiSettings()

    expected_path = Path.home() / ".cowork" / "data" / "cowork.db"
    assert settings.database_url == f"sqlite:///{expected_path}"
    assert settings.app_callback_scheme == "cowork"


def test_non_development_env_requires_internal_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        CoreApiSettings()


def test_non_desktop_defaults_callback_to_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("APP_CALLBACK_SCHEME", raising=False)

    settings = CoreApiSettings()

    assert settings.app_callback_scheme == "http://localhost:5173"


def test_sqlite_schema_compatibility_backfills_skill_and_memorynote_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE skill (
                    id INTEGER PRIMARY KEY NOT NULL,
                    skill_id VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    description VARCHAR NOT NULL,
                    source VARCHAR NOT NULL,
                    domains JSON,
                    trigger_keywords JSON,
                    trigger_extensions JSON,
                    owner_user_id INTEGER,
                    storage_path VARCHAR,
                    enabled_by_default BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE memorynote (
                    id INTEGER PRIMARY KEY NOT NULL,
                    user_id INTEGER NOT NULL,
                    project_id VARCHAR NOT NULL,
                    task_id VARCHAR,
                    category VARCHAR NOT NULL,
                    content VARCHAR NOT NULL,
                    pinned BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )

    ensure_sqlite_schema_compatibility(engine)

    with engine.connect() as conn:
        skill_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info('skill')")}
        memory_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info('memorynote')")}
        skill_indexes = {row[1] for row in conn.exec_driver_sql("PRAGMA index_list('skill')")}
        memory_indexes = {row[1] for row in conn.exec_driver_sql("PRAGMA index_list('memorynote')")}

    assert {"trust_state", "security_scan_status", "security_warnings", "provenance", "last_scanned_at"} <= skill_columns
    assert {"confidence", "provenance", "auto_generated", "expires_at"} <= memory_columns
    assert {"ix_skill_trust_state", "ix_skill_security_scan_status"} <= skill_indexes
    assert {"ix_memorynote_auto_generated", "ix_memorynote_expires_at"} <= memory_indexes


def test_sqlite_schema_compatibility_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-idempotent.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE skill (
                    id INTEGER PRIMARY KEY NOT NULL,
                    skill_id VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    description VARCHAR NOT NULL,
                    source VARCHAR NOT NULL,
                    enabled_by_default BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE memorynote (
                    id INTEGER PRIMARY KEY NOT NULL,
                    user_id INTEGER NOT NULL,
                    project_id VARCHAR NOT NULL,
                    category VARCHAR NOT NULL,
                    content VARCHAR NOT NULL,
                    pinned BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )

    ensure_sqlite_schema_compatibility(engine)
    ensure_sqlite_schema_compatibility(engine)

    with engine.connect() as conn:
        skill_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info('skill')")]
        memory_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info('memorynote')")]

    assert skill_columns.count("trust_state") == 1
    assert memory_columns.count("auto_generated") == 1
