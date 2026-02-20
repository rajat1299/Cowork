from __future__ import annotations

import asyncio
from contextvars import copy_context
import inspect
import json
import logging
import threading
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import Any, Callable, TypeVar

from app.runtime.events import StepEvent
from app.runtime.tool_context import current_agent_name, current_process_task_id

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
        except Exception:
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


def _emit_tool_event(toolkit: Any, step: StepEvent, message: str) -> None:
    event_stream = getattr(toolkit, "event_stream", None)
    if event_stream is None:
        return
    agent_name = getattr(toolkit, "agent_name", "") or current_agent_name.get("")
    process_task_id = current_process_task_id.get("")
    toolkit_name = getattr(toolkit, "toolkit_name", None)
    if callable(toolkit_name):
        toolkit_name = toolkit_name()
    if not toolkit_name:
        toolkit_name = toolkit.__class__.__name__
    method_name = getattr(toolkit, "current_method_name", "")
    event_stream.emit(
        step,
        {
            "agent_name": agent_name,
            "process_task_id": process_task_id,
            "toolkit_name": toolkit_name,
            "method_name": method_name.replace("_", " "),
            "message": message,
        },
    )


async def _ensure_tool_approval(toolkit: Any, method_name: str, args: tuple, kwargs: dict) -> None:
    callback = getattr(toolkit, "approval_callback", None)
    if not callable(callback):
        return

    toolkit_name = getattr(toolkit, "toolkit_name", None)
    if callable(toolkit_name):
        toolkit_name = toolkit_name()
    if not toolkit_name:
        toolkit_name = toolkit.__class__.__name__

    decision = callback(
        toolkit_name=toolkit_name,
        method_name=method_name,
        args=args,
        kwargs=kwargs,
        message=_format_args((toolkit, *args), kwargs),
        agent_name=getattr(toolkit, "agent_name", "") or current_agent_name.get(""),
        process_task_id=current_process_task_id.get(""),
    )
    if inspect.iscoroutine(decision):
        decision = await decision

    if decision is False:
        raise PermissionError(f"Tool execution denied for {toolkit_name}.{method_name}")


def _ensure_tool_approval_sync(toolkit: Any, method_name: str, args: tuple, kwargs: dict) -> None:
    callback = getattr(toolkit, "approval_callback", None)
    if not callable(callback):
        return

    decision = callback(
        toolkit_name=(
            toolkit.toolkit_name() if callable(getattr(toolkit, "toolkit_name", None)) else toolkit.__class__.__name__
        ),
        method_name=method_name,
        args=args,
        kwargs=kwargs,
        message=_format_args((toolkit, *args), kwargs),
        agent_name=getattr(toolkit, "agent_name", "") or current_agent_name.get(""),
        process_task_id=current_process_task_id.get(""),
    )
    if inspect.iscoroutine(decision):
        decision = _run_async_in_sync(decision)

    if decision is False:
        raise PermissionError(f"Tool execution denied for {toolkit.__class__.__name__}.{method_name}")


def listen_toolkit(base_method: Callable[..., Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if iscoroutinefunction(base_method):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                toolkit = args[0]
                toolkit.current_method_name = func.__name__
                await _ensure_tool_approval(toolkit, func.__name__, args[1:], kwargs)
                _emit_tool_event(toolkit, StepEvent.activate_toolkit, _format_args(args, kwargs))
                error = None
                result = None
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    error = exc
                _emit_tool_event(toolkit, StepEvent.deactivate_toolkit, _safe_result_message(result, error))
                if error is not None:
                    raise error
                return result

            async_wrapper.__signature__ = signature(base_method)
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            toolkit = args[0]
            toolkit.current_method_name = func.__name__
            _ensure_tool_approval_sync(toolkit, func.__name__, args[1:], kwargs)
            _emit_tool_event(toolkit, StepEvent.activate_toolkit, _format_args(args, kwargs))
            error = None
            result = None
            try:
                result = func(*args, **kwargs)
                # Handle async functions called from sync context
                if inspect.iscoroutine(result):
                    logger.debug(f"Running async method {func.__name__} in sync context")
                    result = _run_async_in_sync(result)
            except Exception as exc:
                error = exc
            _emit_tool_event(toolkit, StepEvent.deactivate_toolkit, _safe_result_message(result, error))
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
