from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, TypedDict

from app.runtime.events import ToolHookPhase
from app.runtime.toolkits.base import Toolkit

_toolkits: dict[str, Toolkit] = {}


def register(toolkit: Toolkit) -> None:
    _toolkits[toolkit.name] = toolkit


def get_toolkit(name: str) -> Toolkit | None:
    return _toolkits.get(name)


def list_toolkits() -> list[str]:
    return sorted(_toolkits.keys())


ToolHookDecision = Literal["allow", "deny"]


class ToolHookContext(TypedDict, total=False):
    toolkit_name: str
    method_name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    message: str
    agent_name: str
    process_task_id: str
    result: Any
    error: str


class ToolHookResult(TypedDict, total=False):
    decision: ToolHookDecision
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    reason: str
    audit_metadata: dict[str, Any]


ToolHookHandlerResult = ToolHookResult | None
ToolHookHandler = Callable[
    [ToolHookContext],
    ToolHookHandlerResult | Awaitable[ToolHookHandlerResult],
]
ToolHookMatcher = Callable[[ToolHookContext], bool]


@dataclass(frozen=True)
class ToolHook:
    name: str
    phases: tuple[ToolHookPhase, ...]
    handler: ToolHookHandler
    matcher: ToolHookMatcher | None = None


class ToolHookAuditEntry(TypedDict):
    hook_name: str
    phase: ToolHookPhase
    decision: ToolHookDecision
    reason: str
    metadata: dict[str, Any]


class ToolHookRunOutcome(TypedDict):
    allowed: bool
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    reason: str
    audit_entries: list[ToolHookAuditEntry]


_tool_hooks: list[ToolHook] = []


def register_tool_hook(hook: ToolHook) -> None:
    global _tool_hooks
    _tool_hooks = [existing for existing in _tool_hooks if existing.name != hook.name]
    _tool_hooks.append(hook)


def list_tool_hooks(phase: ToolHookPhase | None = None) -> list[ToolHook]:
    if phase is None:
        return list(_tool_hooks)
    return [hook for hook in _tool_hooks if phase in hook.phases]


def clear_tool_hooks() -> None:
    _tool_hooks.clear()


def build_tool_hook_matcher(
    *,
    toolkit_names: set[str] | None = None,
    method_names: set[str] | None = None,
    toolkit_contains: set[str] | None = None,
    method_contains: set[str] | None = None,
) -> ToolHookMatcher:
    normalized_toolkits = {value.strip().lower() for value in toolkit_names or set() if value}
    normalized_methods = {value.strip().lower() for value in method_names or set() if value}
    toolkit_fragments = {value.strip().lower() for value in toolkit_contains or set() if value}
    method_fragments = {value.strip().lower() for value in method_contains or set() if value}

    def _matcher(context: ToolHookContext) -> bool:
        toolkit_name = str(context.get("toolkit_name") or "").strip().lower()
        method_name = str(context.get("method_name") or "").strip().lower()
        if normalized_toolkits and toolkit_name not in normalized_toolkits:
            return False
        if normalized_methods and method_name not in normalized_methods:
            return False
        if toolkit_fragments and not any(fragment in toolkit_name for fragment in toolkit_fragments):
            return False
        if method_fragments and not any(fragment in method_name for fragment in method_fragments):
            return False
        return True

    return _matcher


async def run_tool_hooks(
    phase: ToolHookPhase,
    *,
    context: ToolHookContext,
) -> ToolHookRunOutcome:
    current_args = tuple(context.get("args", ()))
    current_kwargs = dict(context.get("kwargs", {}))
    audit_entries: list[ToolHookAuditEntry] = []

    for hook in list_tool_hooks(phase):
        hook_context: ToolHookContext = {
            **context,
            "args": current_args,
            "kwargs": current_kwargs,
        }
        if hook.matcher is not None and not hook.matcher(hook_context):
            continue
        try:
            hook_result = hook.handler(hook_context)
            if inspect.isawaitable(hook_result):
                hook_result = await hook_result
        except Exception as exc:
            reason = f"hook_error:{hook.name}:{exc}"
            audit_entries.append(
                {
                    "hook_name": hook.name,
                    "phase": phase,
                    "decision": "deny",
                    "reason": reason,
                    "metadata": {},
                }
            )
            return {
                "allowed": False,
                "args": current_args,
                "kwargs": current_kwargs,
                "reason": reason,
                "audit_entries": audit_entries,
            }

        parsed: ToolHookResult = hook_result or {}
        decision_raw = parsed.get("decision", "allow")
        decision: ToolHookDecision = "deny" if decision_raw == "deny" else "allow"
        next_args = parsed.get("args")
        if next_args is not None:
            current_args = tuple(next_args)
        next_kwargs = parsed.get("kwargs")
        if next_kwargs is not None:
            current_kwargs = dict(next_kwargs)
        reason = str(parsed.get("reason") or "")
        metadata_raw = parsed.get("audit_metadata")
        metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
        audit_entries.append(
            {
                "hook_name": hook.name,
                "phase": phase,
                "decision": decision,
                "reason": reason,
                "metadata": metadata,
            }
        )
        if decision == "deny":
            return {
                "allowed": False,
                "args": current_args,
                "kwargs": current_kwargs,
                "reason": reason or f"hook_denied:{hook.name}",
                "audit_entries": audit_entries,
            }

    return {
        "allowed": True,
        "args": current_args,
        "kwargs": current_kwargs,
        "reason": "",
        "audit_entries": audit_entries,
    }
