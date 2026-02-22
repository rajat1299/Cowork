from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Literal, Protocol

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
ToolApprovalTier = Literal["always_ask", "ask_once", "never_ask"]

_FILE_DESTRUCTIVE_KEYWORDS = {"delete", "remove", "rename", "move"}
_FILE_ASK_ONCE_KEYWORDS = {"write", "edit", "append", "create", "mkdir", "touch", "copy"}
_MEMORY_EDIT_KEYWORDS = {"write", "edit", "append", "create", "delete", "remove", "update", "set", "pin"}
_COMMUNICATION_TOOLKIT_KEYWORDS = {"gmail", "slack", "lark", "whatsapp"}
_ASK_ONCE_TOOLKIT_KEYWORDS = {
    "excel",
    "pptx",
    "notion",
    "google_calendar",
    "google_drive_mcp",
    "web_deploy",
    "image_generation",
}
_GITHUB_WRITE_KEYWORDS = {
    "create",
    "open",
    "submit",
    "push",
    "merge",
    "delete",
    "close",
    "update",
    "edit",
    "write",
    "comment",
    "approve",
    "review",
    "label",
    "assign",
}
_GITHUB_READ_KEYWORDS = {"list", "get", "read", "search", "fetch", "view"}


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


def _normalize_tool_method(toolkit_name: str, method_name: str) -> tuple[str, str]:
    toolkit = (toolkit_name or "").strip().lower().replace(" ", "_")
    method = (method_name or "").strip().lower().replace(" ", "_")
    return toolkit, method


def _approval_memory_key(toolkit_name: str) -> str:
    toolkit = (toolkit_name or "").lower()
    return "".join(ch for ch in toolkit if ch.isalnum())


def _contains_any(text: str, keywords: set[str]) -> bool:
    compact_text = text.replace("_", "")
    return any(
        keyword in text or keyword.replace("_", "") in compact_text
        for keyword in keywords
    )


def _github_is_write_action(method: str) -> bool:
    if _contains_any(method, _GITHUB_WRITE_KEYWORDS):
        return True
    if _contains_any(method, _GITHUB_READ_KEYWORDS):
        return False
    # Unknown github operations default to read-only unless clearly mutating.
    return False


def _tool_approval_tier(toolkit_name: str, method_name: str) -> ToolApprovalTier:
    toolkit, method = _normalize_tool_method(toolkit_name, method_name)

    if "terminal" in toolkit:
        return "always_ask"
    if "codeexecution" in toolkit or "code_execution" in toolkit:
        return "always_ask"
    if "pyautogui" in toolkit:
        return "always_ask"
    if _contains_any(toolkit, _COMMUNICATION_TOOLKIT_KEYWORDS):
        return "always_ask"
    if "memory" in toolkit:
        if _contains_any(method, _MEMORY_EDIT_KEYWORDS):
            return "always_ask"
        return "never_ask"
    if "file" in toolkit:
        if _contains_any(method, _FILE_DESTRUCTIVE_KEYWORDS):
            return "always_ask"
        if _contains_any(method, _FILE_ASK_ONCE_KEYWORDS):
            return "ask_once"
        return "never_ask"
    if "github" in toolkit:
        return "ask_once" if _github_is_write_action(method) else "never_ask"
    if _contains_any(toolkit, _ASK_ONCE_TOOLKIT_KEYWORDS):
        return "ask_once"

    return "never_ask"


def _requires_tool_permission(toolkit_name: str, method_name: str) -> bool:
    return _tool_approval_tier(toolkit_name, method_name) != "never_ask"


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


def _friendly_agent_name(agent_name: str) -> str:
    cleaned = (agent_name or "").strip().replace("_", " ")
    if cleaned.endswith(" agent"):
        cleaned = cleaned[:-6]
    if not cleaned:
        return "Cowork"
    return cleaned.title()


def _summarize_permission_detail(message: str) -> str | None:
    text = " ".join((message or "").split())
    if not text:
        return None
    if len(text) > 200:
        return f"{text[:197]}..."
    return text


def _human_readable_permission(toolkit_name: str, method_name: str, message: str) -> tuple[str, str | None]:
    toolkit, method = _normalize_tool_method(toolkit_name, method_name)
    action = "run this tool action"

    if "file" in toolkit:
        if _contains_any(method, _FILE_DESTRUCTIVE_KEYWORDS):
            action = "modify or delete files"
        elif "mkdir" in method:
            action = "create a folder"
        else:
            action = "create a file"
    elif "terminal" in toolkit:
        action = "run a terminal command"
    elif "codeexecution" in toolkit or "code_execution" in toolkit:
        action = "execute code"
    elif "gmail" in toolkit:
        action = "send an email on your behalf"
    elif any(keyword in toolkit for keyword in {"slack", "lark", "whatsapp"}):
        action = "send a message on your behalf"
    elif "pyautogui" in toolkit:
        action = "control your computer"
    elif "github" in toolkit:
        action = "update GitHub content"
    elif "memory" in toolkit and _contains_any(method, _MEMORY_EDIT_KEYWORDS):
        action = "edit saved memory"
    elif any(keyword in toolkit for keyword in {"excel", "pptx"}):
        action = "create or update a document"
    elif "notion" in toolkit:
        action = "update Notion content"
    elif "google_calendar" in toolkit:
        action = "create or update calendar events"
    elif "google_drive_mcp" in toolkit:
        action = "upload or modify Drive files"
    elif "web_deploy" in toolkit:
        action = "deploy content to the web"
    elif "image_generation" in toolkit:
        action = "generate an image file"

    return f"Allow the assistant to {action}?", _summarize_permission_detail(message)


async def _request_tool_permission(
    task_lock: TaskLock,
    event_stream: _PermissionEventStream,
    toolkit_name: str,
    method_name: str,
    message: str,
    agent_name: str,
    process_task_id: str,
) -> bool:
    tier = _tool_approval_tier(toolkit_name, method_name)
    if tier == "never_ask":
        return True
    toolkit_key = _approval_memory_key(toolkit_name)
    if tier == "ask_once" and toolkit_key in task_lock.remembered_approvals:
        return True

    human_question, detail = _human_readable_permission(toolkit_name, method_name, message)
    agent_display_name = _friendly_agent_name(agent_name)
    human_question = human_question.replace("the assistant", agent_display_name, 1)

    request_id = uuid.uuid4().hex
    response_queue = task_lock.human_input.setdefault(request_id, asyncio.Queue(maxsize=1))
    task_lock.pending_approval_context[request_id] = {
        "tier": tier,
        "toolkit_key": toolkit_key,
    }
    event_stream.emit(
        StepEvent.ask_user,
        {
            "type": "tool_approval",
            "question": human_question,
            "request_id": request_id,
            "human_question": human_question,
            "detail": detail,
            "tier": tier,
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
                        "tier": tier,
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
                        "tier": tier,
                        "toolkit_name": toolkit_name,
                        "method_name": method_name,
                    },
                )
            return approved
    finally:
        task_lock.human_input.pop(request_id, None)
        task_lock.pending_approval_context.pop(request_id, None)
