from __future__ import annotations

import asyncio
from contextvars import copy_context
import inspect
import json
import logging
import threading
import uuid
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import Any, Callable, Literal, TypeVar, TypedDict

from pydantic import BaseModel, ValidationError

from app.runtime.events import StepEvent, ToolAuditEvent, ToolHookPhase
from app.runtime.tool_context import current_agent_name, current_process_task_id
from app.runtime.toolkits.registry import ToolHookAuditEntry, run_tool_hooks

logger = logging.getLogger(__name__)

# Thread-local storage for event loops
_thread_local = threading.local()


def _run_async_in_sync(coro):
    """Run an async coroutine from a synchronous context."""
    try:
        loop = asyncio.get_running_loop()
        # There's a running loop but we're in a sync function
        ctx = copy_context()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: ctx.run(asyncio.run, coro))
            return future.result(timeout=60)
    except RuntimeError:
        # No running event loop
        ctx = copy_context()
        if not hasattr(_thread_local, "loop") or _thread_local.loop.is_closed():
            _thread_local.loop = asyncio.new_event_loop()
        loop = _thread_local.loop
        try:
            return ctx.run(loop.run_until_complete, coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            _thread_local.loop = loop
            return ctx.run(loop.run_until_complete, coro)


EXCLUDED_METHODS = {
    "get_tools",
    "get_can_use_tools",
    "toolkit_name",
    "clone_for_new_session",
    "model_dump",
    "model_dump_json",
    "dict",
    "json",
    "copy",
    "update",
}

T = TypeVar("T")


class ToolExecutionContext(TypedDict):
    toolkit_name: str
    method_name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    message: str
    agent_name: str
    process_task_id: str
    request_id: str


class ToolLifecyclePayload(BaseModel):
    agent_name: str
    process_task_id: str
    toolkit_name: str
    method_name: str
    message: str


class ToolResultPayload(ToolLifecyclePayload):
    contract_version: Literal["tool_result_v1"] = "tool_result_v1"
    success: bool
    output: str
    error: str | None = None


def _format_args(args: tuple, kwargs: dict) -> str:
    filtered_args = args[1:] if len(args) > 0 else []
    parts = [repr(arg) for arg in filtered_args]
    if kwargs:
        parts.extend(f"{key}={value!r}" for key, value in kwargs.items())
    args_str = ", ".join(parts)
    if len(args_str) > 500:
        return args_str[:500] + f"... (truncated, total length: {len(args_str)} chars)"
    return args_str


def _safe_result_message(result: Any, error: Exception | None) -> str:
    if error is not None:
        return str(error)
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except TypeError:
        result_str = str(result)
        if len(result_str) > 500:
            return result_str[:500] + f"... (truncated, total length: {len(result_str)} chars)"
        return result_str


def _resolve_toolkit_name(toolkit: Any) -> str:
    toolkit_name = getattr(toolkit, "toolkit_name", None)
    if callable(toolkit_name):
        toolkit_name = toolkit_name()
    if not toolkit_name:
        toolkit_name = toolkit.__class__.__name__
    return str(toolkit_name)


def _short_audit_message(message: str) -> str:
    normalized = " ".join(str(message or "").split())
    if len(normalized) > 200:
        return f"{normalized[:197]}..."
    return normalized


def _build_tool_execution_context(
    toolkit: Any,
    method_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> ToolExecutionContext:
    toolkit_name = _resolve_toolkit_name(toolkit)
    agent_name = getattr(toolkit, "agent_name", "") or current_agent_name.get("")
    process_task_id = current_process_task_id.get("")
    message = _format_args((toolkit, *args), kwargs)
    return {
        "toolkit_name": toolkit_name,
        "method_name": method_name,
        "args": tuple(args),
        "kwargs": dict(kwargs),
        "message": message,
        "agent_name": agent_name,
        "process_task_id": process_task_id,
        "request_id": uuid.uuid4().hex,
    }


def _emit_tool_event(
    toolkit: Any,
    step: StepEvent,
    message: str,
    *,
    success: bool | None = None,
    error: str | None = None,
) -> None:
    event_stream = getattr(toolkit, "event_stream", None)
    if event_stream is None:
        return
    agent_name = getattr(toolkit, "agent_name", "") or current_agent_name.get("")
    process_task_id = current_process_task_id.get("")
    toolkit_name = _resolve_toolkit_name(toolkit)
    method_name = getattr(toolkit, "current_method_name", "")
    try:
        if step == StepEvent.deactivate_toolkit:
            payload = ToolResultPayload(
                agent_name=agent_name,
                process_task_id=process_task_id,
                toolkit_name=toolkit_name,
                method_name=method_name.replace("_", " "),
                message=message,
                success=bool(success),
                output=message if success is not False else "",
                error=error,
            ).model_dump(exclude_none=True)
        else:
            payload = ToolLifecyclePayload(
                agent_name=agent_name,
                process_task_id=process_task_id,
                toolkit_name=toolkit_name,
                method_name=method_name.replace("_", " "),
                message=message,
            ).model_dump()
    except ValidationError as exc:
        logger.warning("tool_event_payload_validation_failed: %s", exc)
        return
    event_stream.emit(step, payload)


def _emit_tool_audit(
    toolkit: Any,
    *,
    context: ToolExecutionContext,
    event_name: ToolAuditEvent,
    outcome: str,
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    event_stream = getattr(toolkit, "event_stream", None)
    if event_stream is None:
        return
    event_stream.emit(
        StepEvent.audit_log,
        {
            "type": "audit_log",
            "event_name": event_name.value,
            "request_id": context["request_id"],
            "channel": "tool_execution",
            "outcome": outcome,
            "actor": "assistant",
            "toolkit_name": context["toolkit_name"],
            "method_name": context["method_name"],
            "agent_name": context["agent_name"],
            "process_task_id": context["process_task_id"],
            "message": _short_audit_message(message or context["message"]),
            "audit_metadata": metadata or {},
        },
    )


def _emit_hook_audits(
    toolkit: Any,
    *,
    context: ToolExecutionContext,
    audit_entries: list[ToolHookAuditEntry],
) -> None:
    for entry in audit_entries:
        hook_metadata = dict(entry["metadata"])
        hook_metadata.update(
            {
                "hook_name": entry["hook_name"],
                "hook_phase": entry["phase"].value,
            }
        )
        _emit_tool_audit(
            toolkit,
            context=context,
            event_name=ToolAuditEvent.hook,
            outcome=entry["decision"],
            message=entry["reason"] or context["message"],
            metadata=hook_metadata,
        )


async def _run_pre_tool_pipeline(
    toolkit: Any,
    method_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> ToolExecutionContext:
    context = _build_tool_execution_context(toolkit, method_name, args, kwargs)
    _emit_tool_audit(
        toolkit,
        context=context,
        event_name=ToolAuditEvent.request,
        outcome="requested",
    )

    hook_outcome = await run_tool_hooks(
        ToolHookPhase.pre_tool_use,
        context={
            "toolkit_name": context["toolkit_name"],
            "method_name": context["method_name"],
            "args": context["args"],
            "kwargs": context["kwargs"],
            "message": context["message"],
            "agent_name": context["agent_name"],
            "process_task_id": context["process_task_id"],
        },
    )
    _emit_hook_audits(toolkit, context=context, audit_entries=hook_outcome["audit_entries"])
    if not hook_outcome["allowed"]:
        reason = hook_outcome["reason"] or "pre_tool_hook_denied"
        _emit_tool_audit(
            toolkit,
            context=context,
            event_name=ToolAuditEvent.decision,
            outcome="denied",
            message=reason,
            metadata={"source": "pre_tool_hook"},
        )
        raise PermissionError(f"Tool execution denied by hook for {context['toolkit_name']}.{method_name}")

    context["args"] = hook_outcome["args"]
    context["kwargs"] = hook_outcome["kwargs"]
    context["message"] = _format_args((toolkit, *context["args"]), context["kwargs"])

    callback = getattr(toolkit, "approval_callback", None)
    if callable(callback):
        decision = callback(
            toolkit_name=context["toolkit_name"],
            method_name=method_name,
            args=context["args"],
            kwargs=context["kwargs"],
            message=context["message"],
            agent_name=context["agent_name"],
            process_task_id=context["process_task_id"],
        )
        if inspect.iscoroutine(decision):
            decision = await decision
        if decision is False:
            _emit_tool_audit(
                toolkit,
                context=context,
                event_name=ToolAuditEvent.decision,
                outcome="denied",
                message="approval_callback_denied",
                metadata={"source": "approval_callback"},
            )
            raise PermissionError(f"Tool execution denied for {context['toolkit_name']}.{method_name}")

    _emit_tool_audit(
        toolkit,
        context=context,
        event_name=ToolAuditEvent.decision,
        outcome="approved",
    )
    return context


async def _run_post_tool_pipeline(
    toolkit: Any,
    *,
    context: ToolExecutionContext,
    result: Any | None = None,
    error: Exception | None = None,
) -> None:
    phase = ToolHookPhase.post_tool_use_failure if error is not None else ToolHookPhase.post_tool_use
    hook_context = {
        "toolkit_name": context["toolkit_name"],
        "method_name": context["method_name"],
        "args": context["args"],
        "kwargs": context["kwargs"],
        "message": context["message"],
        "agent_name": context["agent_name"],
        "process_task_id": context["process_task_id"],
    }
    if error is not None:
        hook_context["error"] = str(error)
    else:
        hook_context["result"] = result

    hook_outcome = await run_tool_hooks(phase, context=hook_context)
    _emit_hook_audits(toolkit, context=context, audit_entries=hook_outcome["audit_entries"])
    if not hook_outcome["allowed"]:
        reason = hook_outcome["reason"] or "post_tool_hook_denied"
        raise PermissionError(f"{reason} for {context['toolkit_name']}.{context['method_name']}")


def listen_toolkit(base_method: Callable[..., Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if iscoroutinefunction(base_method):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                toolkit = args[0]
                toolkit.current_method_name = func.__name__
                execution_context = await _run_pre_tool_pipeline(
                    toolkit,
                    func.__name__,
                    tuple(args[1:]),
                    dict(kwargs),
                )
                _emit_tool_audit(
                    toolkit,
                    context=execution_context,
                    event_name=ToolAuditEvent.execution,
                    outcome="started",
                )
                _emit_tool_event(toolkit, StepEvent.activate_toolkit, execution_context["message"])
                error = None
                result = None
                try:
                    result = await func(toolkit, *execution_context["args"], **execution_context["kwargs"])
                    await _run_post_tool_pipeline(
                        toolkit,
                        context=execution_context,
                        result=result,
                    )
                except Exception as exc:
                    error = exc
                    try:
                        await _run_post_tool_pipeline(
                            toolkit,
                            context=execution_context,
                            error=exc,
                        )
                    except Exception as post_exc:
                        error = post_exc
                    _emit_tool_audit(
                        toolkit,
                        context=execution_context,
                        event_name=ToolAuditEvent.failure,
                        outcome="failed",
                        message=str(error),
                    )
                _emit_tool_event(
                    toolkit,
                    StepEvent.deactivate_toolkit,
                    _safe_result_message(result, error),
                    success=error is None,
                    error=str(error) if error is not None else None,
                )
                if error is not None:
                    raise error
                return result

            async_wrapper.__signature__ = signature(base_method)
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            toolkit = args[0]
            toolkit.current_method_name = func.__name__
            execution_context = _run_async_in_sync(
                _run_pre_tool_pipeline(
                    toolkit,
                    func.__name__,
                    tuple(args[1:]),
                    dict(kwargs),
                )
            )
            _emit_tool_audit(
                toolkit,
                context=execution_context,
                event_name=ToolAuditEvent.execution,
                outcome="started",
            )
            _emit_tool_event(toolkit, StepEvent.activate_toolkit, execution_context["message"])
            error = None
            result = None
            try:
                result = func(toolkit, *execution_context["args"], **execution_context["kwargs"])
                # Handle async functions called from sync context
                if inspect.iscoroutine(result):
                    logger.debug(f"Running async method {func.__name__} in sync context")
                    result = _run_async_in_sync(result)
                _run_async_in_sync(
                    _run_post_tool_pipeline(
                        toolkit,
                        context=execution_context,
                        result=result,
                    )
                )
            except Exception as exc:
                error = exc
                try:
                    _run_async_in_sync(
                        _run_post_tool_pipeline(
                            toolkit,
                            context=execution_context,
                            error=exc,
                        )
                    )
                except Exception as post_exc:
                    error = post_exc
                _emit_tool_audit(
                    toolkit,
                    context=execution_context,
                    event_name=ToolAuditEvent.failure,
                    outcome="failed",
                    message=str(error),
                )
            _emit_tool_event(
                toolkit,
                StepEvent.deactivate_toolkit,
                _safe_result_message(result, error),
                success=error is None,
                error=str(error) if error is not None else None,
            )
            if error is not None:
                raise error
            return result

        sync_wrapper.__signature__ = signature(base_method)
        return sync_wrapper

    return decorator


def auto_listen_toolkit(base_toolkit_class: type[T]) -> Callable[[type[T]], type[T]]:
    def class_decorator(cls: type[T]) -> type[T]:
        for method_name in dir(base_toolkit_class):
            if method_name.startswith("_") or method_name in EXCLUDED_METHODS:
                continue
            base_method = getattr(base_toolkit_class, method_name, None)
            if not callable(base_method):
                continue
            if method_name in cls.__dict__:
                overridden_method = cls.__dict__[method_name]
                decorated = listen_toolkit(base_method)(overridden_method)
                setattr(cls, method_name, decorated)
                continue

            base_sig = signature(base_method)

            def _unwrap_method(method: Callable[..., Any]) -> Callable[..., Any]:
                while hasattr(method, "__wrapped__"):
                    method = method.__wrapped__  # type: ignore[attr-defined]
                return method

            def _create_wrapper(method_name: str, base_method: Callable[..., Any]) -> Callable[..., Any]:
                unwrapped_method = _unwrap_method(base_method)
                if iscoroutinefunction(unwrapped_method):
                    async def async_method_wrapper(self, *args, **kwargs):
                        return await getattr(super(cls, self), method_name)(*args, **kwargs)

                    async_method_wrapper.__name__ = method_name
                    async_method_wrapper.__signature__ = base_sig
                    return async_method_wrapper

                def sync_method_wrapper(self, *args, **kwargs):
                    result = getattr(super(cls, self), method_name)(*args, **kwargs)
                    if inspect.iscoroutine(result):
                        result = _run_async_in_sync(result)
                    return result

                sync_method_wrapper.__name__ = method_name
                sync_method_wrapper.__signature__ = base_sig
                return sync_method_wrapper

            wrapper = _create_wrapper(method_name, base_method)
            decorated = listen_toolkit(base_method)(wrapper)
            setattr(cls, method_name, decorated)

        return cls

    return class_decorator
