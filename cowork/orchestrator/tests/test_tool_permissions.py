from __future__ import annotations

import pytest

from app.runtime.events import StepEvent, ToolHookPhase
from app.runtime.toolkits.camel_listen import auto_listen_toolkit
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


@auto_listen_toolkit(_BaseToolkit)
class _FailingToolkit(_BaseToolkit):
    def __init__(self, event_stream: _EventStreamStub) -> None:
        self.event_stream = event_stream
        self.agent_name = "developer_agent"

    def execute(self, command: str) -> str:
        raise RuntimeError(f"failed: {command}")


@pytest.fixture(autouse=True)
def _reset_tool_hooks() -> None:
    clear_tool_hooks()
    yield
    clear_tool_hooks()


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
    tool_steps = [step for step, _ in stream.events if step in {StepEvent.activate_toolkit, StepEvent.deactivate_toolkit}]
    assert tool_steps == [
        StepEvent.activate_toolkit,
        StepEvent.deactivate_toolkit,
    ]
    audit_names = [payload.get("event_name") for step, payload in stream.events if step == StepEvent.audit_log]
    assert "tool_execution_request" in audit_names
    assert "tool_execution_decision" in audit_names
    assert "tool_execution_started" in audit_names


def test_tool_hook_pre_can_mutate_input_before_execution_and_approval():
    stream = _EventStreamStub()
    toolkit = _TestToolkit(stream)
    captured = {"message": ""}

    def allow_callback(**kwargs) -> bool:
        captured["message"] = str(kwargs.get("message") or "")
        return True

    toolkit.approval_callback = allow_callback
    register_tool_hook(
        ToolHook(
            name="rewrite_execute_input",
            phases=(ToolHookPhase.pre_tool_use,),
            matcher=build_tool_hook_matcher(method_names={"execute"}),
            handler=lambda _context: {
                "decision": "allow",
                "args": ("echo rewritten",),
                "audit_metadata": {"rule": "rewrite"},
            },
        )
    )

    result = toolkit.execute("echo hello")

    assert result == "ran: echo rewritten"
    assert "echo rewritten" in captured["message"]
    hook_audits = [
        payload
        for step, payload in stream.events
        if step == StepEvent.audit_log and payload.get("event_name") == "tool_hook_evaluated"
    ]
    assert hook_audits
    assert any((payload.get("audit_metadata") or {}).get("rule") == "rewrite" for payload in hook_audits)


def test_tool_hook_pre_can_deny_without_calling_permission_callback():
    stream = _EventStreamStub()
    toolkit = _TestToolkit(stream)
    called = {"value": False}

    def allow_callback(**_kwargs) -> bool:
        called["value"] = True
        return True

    toolkit.approval_callback = allow_callback
    register_tool_hook(
        ToolHook(
            name="deny_execute",
            phases=(ToolHookPhase.pre_tool_use,),
            matcher=build_tool_hook_matcher(method_names={"execute"}),
            handler=lambda _context: {"decision": "deny", "reason": "blocked_by_test_policy"},
        )
    )

    with pytest.raises(PermissionError):
        toolkit.execute("echo hello")

    assert called["value"] is False
    assert toolkit.executed is False
    decision_events = [
        payload
        for step, payload in stream.events
        if step == StepEvent.audit_log and payload.get("event_name") == "tool_execution_decision"
    ]
    assert decision_events
    assert decision_events[-1].get("outcome") == "denied"


def test_tool_hook_failure_phase_runs_and_emits_audit_metadata():
    stream = _EventStreamStub()
    toolkit = _FailingToolkit(stream)

    def allow_callback(**_kwargs) -> bool:
        return True

    toolkit.approval_callback = allow_callback
    register_tool_hook(
        ToolHook(
            name="failure_classifier",
            phases=(ToolHookPhase.post_tool_use_failure,),
            handler=lambda _context: {
                "decision": "allow",
                "audit_metadata": {"classification": "expected_failure"},
            },
        )
    )

    with pytest.raises(RuntimeError):
        toolkit.execute("explode")

    hook_audits = [
        payload
        for step, payload in stream.events
        if step == StepEvent.audit_log and payload.get("event_name") == "tool_hook_evaluated"
    ]
    assert hook_audits
    assert any(
        (payload.get("audit_metadata") or {}).get("classification") == "expected_failure"
        for payload in hook_audits
    )
    failure_audits = [
        payload
        for step, payload in stream.events
        if step == StepEvent.audit_log and payload.get("event_name") == "tool_execution_failure"
    ]
    assert failure_audits
