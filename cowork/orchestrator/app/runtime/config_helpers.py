from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Protocol

from app.runtime.events import StepEvent
from app.runtime.task_lock import TaskLock


_PERMISSION_APPROVE_VALUES = {
    "1",
    "true",
    "yes",
    "y",
    "approve",
    "approved",
    "allow",
    "allowed",
    "ok",
    "proceed",
    "continue",
}
_PERMISSION_DENY_VALUES = {
    "0",
    "false",
    "no",
    "n",
    "deny",
    "denied",
    "reject",
    "rejected",
    "block",
    "stop",
}
_FILE_MUTATION_KEYWORDS = {
    "write",
    "edit",
    "append",
    "create",
    "delete",
    "remove",
    "rename",
    "move",
    "copy",
    "mkdir",
    "touch",
}


class _PermissionEventStream(Protocol):
    def emit(self, step: StepEvent, data: dict) -> None:
        pass


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _config_flag(configs: list[dict[str, Any]], name: str, default: bool = False) -> bool:
    for item in configs:
        key = item.get("key") or item.get("name")
        if key != name:
            continue
        value = item.get("value")
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return default


def _apply_env_overrides(overrides: dict[str, str]) -> dict[str, str | None]:
    previous: dict[str, str | None] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _requires_tool_permission(toolkit_name: str, method_name: str) -> bool:
    toolkit = (toolkit_name or "").lower()
    method = (method_name or "").lower().replace(" ", "_")
    if "terminal" in toolkit:
        return True
    if "codeexecution" in toolkit or "code_execution" in toolkit:
        return True
    if "file" in toolkit:
        return any(keyword in method for keyword in _FILE_MUTATION_KEYWORDS)
    return False


def _is_permission_approved(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    if normalized in _PERMISSION_APPROVE_VALUES:
        return True
    if normalized in _PERMISSION_DENY_VALUES:
        return False
    return False


def _tool_permission_timeout_seconds() -> float:
    raw = os.environ.get("TOOL_PERMISSION_TIMEOUT_SECONDS", "120")
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return 120.0


def _default_tool_permission_allow() -> bool:
    if os.environ.get("TOOL_PERMISSION_DEFAULT_ALLOW") is not None:
        return _env_flag("TOOL_PERMISSION_DEFAULT_ALLOW", default=False)
    return os.environ.get("APP_ENV", "development").strip().lower() == "development"


async def _request_tool_permission(
    task_lock: TaskLock,
    event_stream: _PermissionEventStream,
    toolkit_name: str,
    method_name: str,
    message: str,
    agent_name: str,
    process_task_id: str,
) -> bool:
    if not _requires_tool_permission(toolkit_name, method_name):
        return True

    request_id = uuid.uuid4().hex
    response_queue = task_lock.human_input.setdefault(request_id, asyncio.Queue(maxsize=1))
    event_stream.emit(
        StepEvent.ask_user,
        {
            "question": (
                f"Allow {agent_name or 'agent'} to run {toolkit_name}.{method_name}?"
            ),
            "request_id": request_id,
            "toolkit_name": toolkit_name,
            "method_name": method_name,
            "agent_name": agent_name,
            "process_task_id": process_task_id,
            "message": message,
        },
    )

    timeout = _tool_permission_timeout_seconds()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if task_lock.stop_requested:
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                approved = _default_tool_permission_allow()
                outcome = "approved" if approved else "denied"
                event_stream.emit(
                    StepEvent.notice,
                    {
                        "message": (
                            f"Permission request timed out for {toolkit_name}.{method_name}; "
                            f"default {outcome}."
                        ),
                        "request_id": request_id,
                        "toolkit_name": toolkit_name,
                        "method_name": method_name,
                    },
                )
                return approved
            try:
                response = await asyncio.wait_for(response_queue.get(), timeout=min(1.0, remaining))
            except asyncio.TimeoutError:
                continue
            approved = _is_permission_approved(response)
            if not approved:
                event_stream.emit(
                    StepEvent.notice,
                    {
                        "message": f"Permission denied for {toolkit_name}.{method_name}.",
                        "request_id": request_id,
                        "toolkit_name": toolkit_name,
                        "method_name": method_name,
                    },
                )
            return approved
    finally:
        task_lock.human_input.pop(request_id, None)
