from __future__ import annotations

from app.runtime.events import StepEvent
from app.runtime.toolkits.camel_listen import _emit_tool_event


class _FakeEventStream:
    def __init__(self) -> None:
        self.events: list[tuple[StepEvent, dict]] = []

    def emit(self, step: StepEvent, data: dict) -> None:
        self.events.append((step, data))


class _FakeToolkit:
    def __init__(self, stream: _FakeEventStream) -> None:
        self.event_stream = stream
        self.agent_name = "writer_agent"
        self.current_method_name = "write_file"

    def toolkit_name(self) -> str:
        return "FileToolkitWithEvents"


def test_emit_tool_result_event_matches_contract_v1() -> None:
    stream = _FakeEventStream()
    toolkit = _FakeToolkit(stream)

    _emit_tool_event(
        toolkit,
        StepEvent.deactivate_toolkit,
        "content successfully written to file",
        success=True,
    )

    assert len(stream.events) == 1
    step, payload = stream.events[0]
    assert step == StepEvent.deactivate_toolkit
    assert payload["contract_version"] == "tool_result_v1"
    assert payload["success"] is True
    assert isinstance(payload["output"], str)
    assert payload["method_name"] == "write file"


def test_emit_tool_start_event_excludes_tool_result_contract_fields() -> None:
    stream = _FakeEventStream()
    toolkit = _FakeToolkit(stream)

    _emit_tool_event(toolkit, StepEvent.activate_toolkit, "calling write_file")

    assert len(stream.events) == 1
    step, payload = stream.events[0]
    assert step == StepEvent.activate_toolkit
    assert "contract_version" not in payload
    assert "success" not in payload
