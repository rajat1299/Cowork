"""Pytest configuration for orchestrator tests."""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _trace_log_to_tmp(monkeypatch, tmp_path):
    """Route runtime trace logs to tmp_path so tests can run in sandbox."""
    log_path = tmp_path / "runtime.log"
    monkeypatch.setenv("COWORK_RUNTIME_LOG_PATH", str(log_path))
    # Reset the trace logger so it picks up the new path
    import app.runtime.tracing as tracing_module

    monkeypatch.setattr(tracing_module, "_TRACE_LOGGER", None)
