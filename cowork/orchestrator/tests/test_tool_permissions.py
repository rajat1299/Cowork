from __future__ import annotations

import pytest

from app.runtime.events import StepEvent
from app.runtime.toolkits.camel_listen import auto_listen_toolkit


class _EventStreamStub:
    def __init__(self) -> None:
        self.events: list[tuple[StepEvent, dict]] = []

    def emit(self, step: StepEvent, data: dict) -> None:
        self.events.append((step, data))


class _BaseToolkit:
    def execute(self, command: str) -> str:
        raise NotImplementedError


@auto_listen_toolkit(_BaseToolkit)
class _TestToolkit(_BaseToolkit):
    def __init__(self, event_stream: _EventStreamStub) -> None:
        self.event_stream = event_stream
        self.agent_name = "developer_agent"
        self.executed = False

    def execute(self, command: str) -> str:
        self.executed = True
        return f"ran: {command}"


def test_tool_wrapper_blocks_execution_when_permission_denied():
    stream = _EventStreamStub()
    toolkit = _TestToolkit(stream)
    called = {"value": False}

    def deny_callback(**_kwargs) -> bool:
        called["value"] = True
        return False

    toolkit.approval_callback = deny_callback

    with pytest.raises(PermissionError):
        toolkit.execute("rm -rf .")

    assert called["value"] is True
    assert toolkit.executed is False


def test_tool_wrapper_allows_execution_when_permission_granted():
    stream = _EventStreamStub()
    toolkit = _TestToolkit(stream)

    def allow_callback(**_kwargs) -> bool:
        return True

    toolkit.approval_callback = allow_callback
    result = toolkit.execute("echo hello")

    assert result == "ran: echo hello"
    assert toolkit.executed is True
    assert [step for step, _ in stream.events] == [
        StepEvent.activate_toolkit,
        StepEvent.deactivate_toolkit,
    ]
