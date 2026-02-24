from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Literal, Protocol

from app.runtime.events import StepEvent
from app.runtime.task_lock import TaskLock
from shared.schemas import INTERACTION_CONTRACT_VERSION


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


def _emit_audit_log(
    event_stream: _PermissionEventStream,
    *,
    event_name: str,
    request_id: str,
    channel: str,
    outcome: str,
    toolkit_name: str = "",
    method_name: str = "",
    tier: str = "",
    message: str | None = None,
    process_task_id: str = "",
    actor: str = "assistant",
) -> None:
    # Keep audit payload compact and immutable so it can be persisted as a timeline record.
    event_stream.emit(
        StepEvent.audit_log,
        {
            "type": "audit_log",
            "event_name": event_name,
            "request_id": request_id,
            "channel": channel,
            "outcome": outcome,
            "actor": actor,
            "toolkit_name": toolkit_name,
            "method_name": method_name,
            "tier": tier,
            "message": _summarize_permission_detail(message or ""),
            "process_task_id": process_task_id,
            "contract_version": INTERACTION_CONTRACT_VERSION,
            "timestamp_ms": int(time.time() * 1000),
        },
    )


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


def _approval_memory_group(toolkit_name: str, method_name: str) -> str | None:
    toolkit, method = _normalize_tool_method(toolkit_name, method_name)

    if "terminal" in toolkit:
        return "terminal_command"
    if "codeexecution" in toolkit or "code_execution" in toolkit:
        return "code_execution"
    if "pyautogui" in toolkit:
        return "computer_control"
    if _contains_any(toolkit, _COMMUNICATION_TOOLKIT_KEYWORDS):
        return "communication_send"
    if "memory" in toolkit and _contains_any(method, _MEMORY_EDIT_KEYWORDS):
        return "memory_edit"
    if "file" in toolkit:
        if _contains_any(method, _FILE_DESTRUCTIVE_KEYWORDS):
            return "file_destructive"
        if _contains_any(method, _FILE_ASK_ONCE_KEYWORDS):
            return "file_write"
        return None
    if "github" in toolkit:
        return "github_write" if _github_is_write_action(method) else None
    if _contains_any(toolkit, _ASK_ONCE_TOOLKIT_KEYWORDS):
        toolkit_key = _approval_memory_key(toolkit_name)
        return f"toolkit_{toolkit_key}" if toolkit_key else None
    return None


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
    memory_group = _approval_memory_group(toolkit_name, method_name)
    toolkit_key = _approval_memory_key(toolkit_name)
    remembered_key = memory_group or toolkit_key
    if remembered_key and remembered_key in task_lock.remembered_approvals:
        return True

    human_question, detail = _human_readable_permission(toolkit_name, method_name, message)
    agent_display_name = _friendly_agent_name(agent_name)
    human_question = human_question.replace("the assistant", agent_display_name, 1)

    request_id = uuid.uuid4().hex
    response_queue = task_lock.human_input.setdefault(request_id, asyncio.Queue(maxsize=1))
    task_lock.pending_approval_context[request_id] = {
        "channel": "tool_approval",
        "tier": tier,
        "toolkit_key": toolkit_key,
        "memory_group": memory_group or "",
        "contract_version": INTERACTION_CONTRACT_VERSION,
    }
    event_stream.emit(
        StepEvent.ask_user,
        {
            "type": "tool_approval",
            "channel": "tool_approval",
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
            "contract_version": INTERACTION_CONTRACT_VERSION,
        },
    )
    _emit_audit_log(
        event_stream,
        event_name="permission_request_emitted",
        request_id=request_id,
        channel="tool_approval",
        outcome="requested",
        toolkit_name=toolkit_name,
        method_name=method_name,
        tier=tier,
        message=message,
        process_task_id=process_task_id,
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
                _emit_audit_log(
                    event_stream,
                    event_name="permission_request_timed_out",
                    request_id=request_id,
                    channel="tool_approval",
                    outcome=outcome,
                    toolkit_name=toolkit_name,
                    method_name=method_name,
                    tier=tier,
                    message=message,
                    process_task_id=process_task_id,
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
            _emit_audit_log(
                event_stream,
                event_name="permission_response_recorded",
                request_id=request_id,
                channel="tool_approval",
                outcome="approved" if approved else "denied",
                toolkit_name=toolkit_name,
                method_name=method_name,
                tier=tier,
                message=message,
                process_task_id=process_task_id,
                actor="user",
            )
            return approved
    finally:
        task_lock.human_input.pop(request_id, None)
        task_lock.pending_approval_context.pop(request_id, None)


# ---- Decision request (human-in-the-loop choices) ----


class DecisionOption:
    """A single option in a user decision prompt."""

    __slots__ = ("id", "label", "description")

    def __init__(self, id: str, label: str, description: str = ""):
        self.id = id
        self.label = label
        self.description = description

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"id": self.id, "label": self.label}
        if self.description:
            d["description"] = self.description
        return d


async def _request_user_decision(
    task_lock: TaskLock,
    event_stream: _PermissionEventStream,
    question: str,
    options: list[DecisionOption],
    *,
    mode: Literal["single_select", "multi_select", "rank"] = "single_select",
    skippable: bool = True,
    timeout_seconds: float = 60.0,
    process_task_id: str = "",
) -> str | None:
    """Emit a decision prompt to the user and wait for their selection.

    Returns the user's response string (option id, comma-separated ids for
    multi_select, or freeform text), or ``None`` on timeout/skip/stop.
    """
    request_id = uuid.uuid4().hex
    response_queue = task_lock.human_input.setdefault(
        request_id, asyncio.Queue(maxsize=1)
    )
    task_lock.pending_approval_context[request_id] = {
        "channel": "decision",
        "contract_version": INTERACTION_CONTRACT_VERSION,
        "mode": mode,
    }
    event_stream.emit(
        StepEvent.ask_user,
        {
            "type": "decision",
            "channel": "decision",
            "question": question,
            "request_id": request_id,
            "mode": mode,
            "options": [opt.to_dict() for opt in options],
            "skippable": skippable,
            "timeout": int(timeout_seconds),
            "process_task_id": process_task_id,
            "contract_version": INTERACTION_CONTRACT_VERSION,
        },
    )
    _emit_audit_log(
        event_stream,
        event_name="decision_request_emitted",
        request_id=request_id,
        channel="decision",
        outcome="requested",
        process_task_id=process_task_id,
        message=question,
    )

    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            if task_lock.stop_requested:
                return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _emit_audit_log(
                    event_stream,
                    event_name="decision_request_timed_out",
                    request_id=request_id,
                    channel="decision",
                    outcome="timed_out",
                    process_task_id=process_task_id,
                    message=question,
                )
                return None
            try:
                response = await asyncio.wait_for(
                    response_queue.get(), timeout=min(1.0, remaining)
                )
            except asyncio.TimeoutError:
                continue
            parsed = str(response).strip() if response else None
            _emit_audit_log(
                event_stream,
                event_name="decision_response_recorded",
                request_id=request_id,
                channel="decision",
                outcome="provided" if parsed else "empty",
                process_task_id=process_task_id,
                message=question,
                actor="user",
            )
            return parsed
    finally:
        task_lock.human_input.pop(request_id, None)
        task_lock.pending_approval_context.pop(request_id, None)


# ---- Compose message (display-only, no response queue) ----


class ComposeVariant:
    """A single variant of a composed message."""

    __slots__ = ("id", "label", "subject", "body")

    def __init__(self, id: str, label: str, body: str, subject: str = ""):
        self.id = id
        self.label = label
        self.subject = subject
        self.body = body

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"id": self.id, "label": self.label, "body": self.body}
        if self.subject:
            d["subject"] = self.subject
        return d


def _emit_compose_message(
    event_stream: _PermissionEventStream,
    platform: str,
    variants: list[ComposeVariant],
    *,
    metadata: dict[str, str] | None = None,
) -> None:
    """Emit a compose_message event for the frontend to render.

    This is display-only — no response queue. The user copies or sends
    the message themselves via the widget's action buttons.
    """
    event_stream.emit(
        StepEvent.compose_message,
        {
            "type": "compose_message",
            "channel": "compose_message",
            "platform": platform,
            "variants": [v.to_dict() for v in variants],
            "metadata": metadata or {},
            "contract_version": INTERACTION_CONTRACT_VERSION,
        },
    )
    _emit_audit_log(
        event_stream,
        event_name="compose_message_emitted",
        request_id=uuid.uuid4().hex,
        channel="compose_message",
        outcome="emitted",
        process_task_id="",
        message=platform,
    )
