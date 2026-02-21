from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import CoreApiSettings


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
