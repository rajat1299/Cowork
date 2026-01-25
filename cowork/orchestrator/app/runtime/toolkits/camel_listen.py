from __future__ import annotations

import json
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import Any, Callable, TypeVar

from app.runtime.events import StepEvent
from app.runtime.tool_context import current_agent_name, current_process_task_id


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


def listen_toolkit(base_method: Callable[..., Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if iscoroutinefunction(base_method):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                toolkit = args[0]
                toolkit.current_method_name = func.__name__
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
            _emit_tool_event(toolkit, StepEvent.activate_toolkit, _format_args(args, kwargs))
            error = None
            result = None
            try:
                result = func(*args, **kwargs)
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

            if iscoroutinefunction(base_method):
                async def async_method_wrapper(self, *args, **kwargs):
                    return await getattr(super(cls, self), method_name)(*args, **kwargs)

                async_method_wrapper.__name__ = method_name
                async_method_wrapper.__signature__ = base_sig
                wrapper = async_method_wrapper
            else:
                def sync_method_wrapper(self, *args, **kwargs):
                    return getattr(super(cls, self), method_name)(*args, **kwargs)

                sync_method_wrapper.__name__ = method_name
                sync_method_wrapper.__signature__ = base_sig
                wrapper = sync_method_wrapper

            decorated = listen_toolkit(base_method)(wrapper)
            setattr(cls, method_name, decorated)

        return cls

    return class_decorator
