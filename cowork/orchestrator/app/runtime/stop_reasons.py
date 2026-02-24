from __future__ import annotations

from enum import StrEnum
from typing import Any


class StopStatus(StrEnum):
    completed = "completed"
    stopped = "stopped"
    error = "error"


class StopReason(StrEnum):
    completed = "completed"
    user_stop = "user_stop"
    provider_not_configured = "provider_not_configured"
    decomposition_failed = "decomposition_failed"
    result_summary_failed = "result_summary_failed"
    model_call_failed = "model_call_failed"
    skill_validation_failed = "skill_validation_failed"
    workforce_execution_failed = "workforce_execution_failed"


def build_completed_end(
    result: str,
    *,
    usage: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": StopStatus.completed.value,
        "stop_reason": StopReason.completed.value,
        "result": result,
        "answer": result,
    }
    if usage is not None:
        payload["usage"] = usage
    if extra:
        payload.update(extra)
    return payload


def build_stopped_end(
    stop_reason: str = StopReason.user_stop.value,
    *,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": StopStatus.stopped.value,
        "stop_reason": stop_reason,
        "result": StopStatus.stopped.value,
        "reason": reason or stop_reason,
    }
    if extra:
        payload.update(extra)
    return payload


def build_error_end(
    stop_reason: str,
    reason: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": StopStatus.error.value,
        "stop_reason": stop_reason,
        "result": StopStatus.error.value,
        "reason": reason,
    }
    if extra:
        payload.update(extra)
    return payload


def build_error_event(
    message: str,
    *,
    stop_reason: str | None = None,
    error_type: str = "runtime_error",
    recoverable: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": message,
        "message": message,
        "error_type": error_type,
        "recoverable": recoverable,
    }
    if stop_reason:
        payload["stop_reason"] = stop_reason
    if extra:
        payload.update(extra)
    return payload
