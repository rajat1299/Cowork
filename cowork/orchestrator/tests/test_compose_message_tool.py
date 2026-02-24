from __future__ import annotations

import pytest

from app.runtime.events import StepEvent, ToolHookPhase
from app.runtime.toolkits.camel_tools import build_agent_tools
from app.runtime.toolkits.registry import (
    ToolHook,
    build_tool_hook_matcher,
    clear_tool_hooks,
    register_tool_hook,
)


class _EventStreamStub:
    def __init__(self) -> None:
        self.events: list[tuple[StepEvent, dict]] = []

    def emit(self, step: StepEvent, data: dict) -> None:
        self.events.append((step, data))


@pytest.fixture(autouse=True)
def _reset_tool_hooks() -> None:
    clear_tool_hooks()
    yield
    clear_tool_hooks()


def test_compose_message_tool_emits_compose_event() -> None:
    stream = _EventStreamStub()
    tools = build_agent_tools(
        ["compose_message"],
        stream,
        "document_agent",
        working_directory="/tmp",
    )

    compose_tool = next(
        tool
        for tool in tools
        if getattr(tool.func, "__name__", "") == "compose_message"
    )
    result = compose_tool.func(
        body="Launch goes live Monday.",
        subject="Launch update",
        platform="email",
        label="Warm",
    )

    assert result["status"] == "rendered"
    compose_events = [event for event in stream.events if event[0] == StepEvent.compose_message]
    assert compose_events
    payload = compose_events[0][1]
    assert payload["platform"] == "email"
    assert payload["variants"][0]["label"] == "Warm"
    assert payload["variants"][0]["body"] == "Launch goes live Monday."


def test_compose_message_tool_normalizes_unknown_platform() -> None:
    stream = _EventStreamStub()
    tools = build_agent_tools(
        ["compose_message"],
        stream,
        "document_agent",
        working_directory="/tmp",
    )

    compose_tool = next(
        tool
        for tool in tools
        if getattr(tool.func, "__name__", "") == "compose_message"
    )
    compose_tool.func(body="Draft body", platform="signal")

    compose_events = [event for event in stream.events if event[0] == StepEvent.compose_message]
    assert compose_events
    assert compose_events[0][1]["platform"] == "generic"


def test_compose_message_tool_honors_permission_callback_denial() -> None:
    stream = _EventStreamStub()
    tools = build_agent_tools(
        ["compose_message"],
        stream,
        "document_agent",
        working_directory="/tmp",
        approval_callback=lambda **_kwargs: False,
    )
    compose_tool = next(
        tool
        for tool in tools
        if getattr(tool.func, "__name__", "") == "compose_message"
    )

    with pytest.raises(PermissionError):
        compose_tool.func(body="Should not render")

    compose_events = [event for event in stream.events if event[0] == StepEvent.compose_message]
    assert compose_events == []


def test_compose_message_tool_pre_hook_mutates_kwargs() -> None:
    stream = _EventStreamStub()
    register_tool_hook(
        ToolHook(
            name="compose_body_override",
            phases=(ToolHookPhase.pre_tool_use,),
            matcher=build_tool_hook_matcher(
                toolkit_contains={"compose_message"},
                method_names={"compose_message"},
            ),
            handler=lambda _context: {
                "decision": "allow",
                "kwargs": {
                    "body": "Mutated body",
                    "platform": "email",
                    "label": "Mutated",
                },
            },
        )
    )
    tools = build_agent_tools(
        ["compose_message"],
        stream,
        "document_agent",
        working_directory="/tmp",
    )
    compose_tool = next(
        tool
        for tool in tools
        if getattr(tool.func, "__name__", "") == "compose_message"
    )
    compose_tool.func(body="Original body", platform="email")

    compose_events = [event for event in stream.events if event[0] == StepEvent.compose_message]
    assert compose_events
    payload = compose_events[0][1]
    assert payload["variants"][0]["body"] == "Mutated body"
    assert payload["variants"][0]["label"] == "Mutated"
