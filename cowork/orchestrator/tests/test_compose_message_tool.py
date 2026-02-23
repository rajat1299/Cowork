from __future__ import annotations

from app.runtime.events import StepEvent
from app.runtime.toolkits.camel_tools import build_agent_tools


class _EventStreamStub:
    def __init__(self) -> None:
        self.events: list[tuple[StepEvent, dict]] = []

    def emit(self, step: StepEvent, data: dict) -> None:
        self.events.append((step, data))


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
