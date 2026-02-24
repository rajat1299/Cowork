from __future__ import annotations

import asyncio

import pytest

from app.runtime.config_helpers import (
    DecisionOption,
    _evaluate_tool_permission_policy,
    _human_readable_permission,
    _normalize_permission_mode,
    _request_tool_permission,
    _request_user_decision,
    _tool_approval_tier,
)
from app.runtime.events import StepEvent
from app.runtime.task_lock import TaskLock
from shared.schemas import INTERACTION_CONTRACT_VERSION


class _EventStreamStub:
    def __init__(self) -> None:
        self.events: list[tuple[StepEvent, dict]] = []

    def emit(self, step: StepEvent, data: dict) -> None:
        self.events.append((step, data))


def test_tool_approval_tier_classifies_sensitive_tools() -> None:
    assert _tool_approval_tier("TerminalToolkitWithEvents", "shell_exec") == "always_ask"
    assert _tool_approval_tier("CodeExecutionToolkitWithEvents", "execute_code") == "always_ask"
    assert _tool_approval_tier("PyAutoGuiToolkit", "click") == "always_ask"
    assert _tool_approval_tier("GmailToolkit", "send_email") == "always_ask"
    assert _tool_approval_tier("FileToolkitWithEvents", "delete_file") == "always_ask"

    assert _tool_approval_tier("FileToolkitWithEvents", "write_to_file") == "ask_once"
    assert _tool_approval_tier("GitHubToolkit", "create_pull_request") == "ask_once"
    assert _tool_approval_tier("NotionToolkit", "append_page") == "ask_once"
    assert _tool_approval_tier("GoogleDriveMcpToolkit", "upload_file") == "ask_once"

    assert _tool_approval_tier("FileToolkitWithEvents", "read_file") == "never_ask"
    assert _tool_approval_tier("GitHubToolkit", "list_pull_requests") == "never_ask"
    assert _tool_approval_tier("BrowserToolkitWithEvents", "search") == "never_ask"


def test_normalize_permission_mode_supports_claude_style_values() -> None:
    assert _normalize_permission_mode(None) == "default"
    assert _normalize_permission_mode("default") == "default"
    assert _normalize_permission_mode("acceptEdits") == "accept_edits"
    assert _normalize_permission_mode("accept_edits") == "accept_edits"
    assert _normalize_permission_mode("plan") == "plan"
    assert _normalize_permission_mode("something-else") == "default"


def test_evaluate_tool_permission_policy_respects_modes_and_remembered_groups() -> None:
    default_decision = _evaluate_tool_permission_policy(
        toolkit_name="TerminalToolkitWithEvents",
        method_name="shell_exec",
        permission_mode="default",
        remembered_approvals=set(),
    )
    assert default_decision["decision"] == "ask"
    assert default_decision["tier"] == "always_ask"

    remembered_decision = _evaluate_tool_permission_policy(
        toolkit_name="FileToolkitWithEvents",
        method_name="write_to_file",
        permission_mode="default",
        remembered_approvals={"file_write"},
    )
    assert remembered_decision["decision"] == "allow"

    accept_edits_decision = _evaluate_tool_permission_policy(
        toolkit_name="FileToolkitWithEvents",
        method_name="delete_file",
        permission_mode="acceptEdits",
        remembered_approvals=set(),
    )
    assert accept_edits_decision["decision"] == "allow"
    assert accept_edits_decision["policy_mode"] == "accept_edits"

    plan_decision = _evaluate_tool_permission_policy(
        toolkit_name="FileToolkitWithEvents",
        method_name="write_to_file",
        permission_mode="plan",
        remembered_approvals=set(),
    )
    assert plan_decision["decision"] == "deny"
    assert plan_decision["policy_mode"] == "plan"


def test_human_readable_permission_returns_plain_language_question_and_detail() -> None:
    question, detail = _human_readable_permission(
        "FileToolkitWithEvents",
        "write_to_file",
        "path='/tmp/report.md'",
    )
    assert question.lower().startswith("allow ")
    assert "create a file" in question.lower()
    assert "report.md" in (detail or "")

    terminal_question, _ = _human_readable_permission(
        "TerminalToolkitWithEvents",
        "execute_command",
        "command='rm -rf tmp'",
    )
    assert "terminal command" in terminal_question.lower()

    gmail_question, _ = _human_readable_permission(
        "GmailToolkit",
        "send_email",
        "to='team@example.com'",
    )
    assert "send an email" in gmail_question.lower()

    code_question, _ = _human_readable_permission(
        "CodeExecutionToolkitWithEvents",
        "execute_code",
        "python='print(1)'",
    )
    assert "execute code" in code_question.lower()


@pytest.mark.asyncio
async def test_request_tool_permission_emits_enriched_payload_and_tracks_ask_once_context() -> None:
    task_lock = TaskLock(project_id="proj-permission")
    stream = _EventStreamStub()

    pending = asyncio.create_task(
        _request_tool_permission(
            task_lock=task_lock,
            event_stream=stream,
            toolkit_name="FileToolkitWithEvents",
            method_name="write_to_file",
            message="path='/tmp/report.md'",
            agent_name="document_agent",
            process_task_id="subtask-1",
        )
    )

    await asyncio.sleep(0)

    assert stream.events
    step, payload = next((item for item in stream.events if item[0] == StepEvent.ask_user))
    assert step == StepEvent.ask_user
    assert payload["tier"] == "ask_once"
    assert payload["human_question"]
    assert payload["detail"]
    assert payload["question"] == payload["human_question"]

    request_id = payload["request_id"]
    assert request_id in task_lock.pending_approval_context
    assert task_lock.pending_approval_context[request_id]["memory_group"] == "file_write"
    response_queue = task_lock.human_input[request_id]
    response_queue.put_nowait("approve")

    approved = await pending
    assert approved is True
    assert task_lock.remembered_approvals == set()
    assert request_id not in task_lock.pending_approval_context

    audit_payloads = [payload for step, payload in stream.events if step == StepEvent.audit_log]
    assert audit_payloads
    assert any(payload.get("event_name") == "permission_request_emitted" for payload in audit_payloads)
    assert any(payload.get("event_name") == "permission_response_recorded" for payload in audit_payloads)
    assert payload["contract_version"] == INTERACTION_CONTRACT_VERSION


@pytest.mark.asyncio
async def test_request_tool_permission_skips_when_permission_group_is_remembered() -> None:
    task_lock = TaskLock(
        project_id="proj-permission",
        remembered_approvals={"terminal_command"},
    )
    stream = _EventStreamStub()

    approved = await _request_tool_permission(
        task_lock=task_lock,
        event_stream=stream,
        toolkit_name="TerminalToolkitWithEvents",
        method_name="shell_exec",
        message="command='echo hello'",
        agent_name="developer_agent",
        process_task_id="subtask-1",
    )

    assert approved is True
    assert stream.events == []


@pytest.mark.asyncio
async def test_request_tool_permission_remembered_file_write_does_not_skip_file_delete() -> None:
    task_lock = TaskLock(
        project_id="proj-permission-boundary",
        remembered_approvals={"file_write"},
    )
    stream = _EventStreamStub()

    pending = asyncio.create_task(
        _request_tool_permission(
            task_lock=task_lock,
            event_stream=stream,
            toolkit_name="FileToolkitWithEvents",
            method_name="delete_file",
            message="path='/tmp/report.md'",
            agent_name="developer_agent",
            process_task_id="subtask-2",
        )
    )

    await asyncio.sleep(0)
    assert stream.events
    step, payload = next((item for item in stream.events if item[0] == StepEvent.ask_user))
    assert step == StepEvent.ask_user
    assert payload["tier"] == "always_ask"

    request_id = str(payload["request_id"])
    task_lock.human_input[request_id].put_nowait("approve")

    approved = await pending
    assert approved is True


@pytest.mark.asyncio
async def test_request_tool_permission_timeout_emits_notice_and_uses_default_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOOL_PERMISSION_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("TOOL_PERMISSION_DEFAULT_ALLOW", "false")

    task_lock = TaskLock(project_id="proj-permission-timeout")
    stream = _EventStreamStub()

    approved = await _request_tool_permission(
        task_lock=task_lock,
        event_stream=stream,
        toolkit_name="TerminalToolkitWithEvents",
        method_name="shell_exec",
        message="command='rm -rf /tmp/scratch'",
        agent_name="developer_agent",
        process_task_id="subtask-timeout",
    )

    assert approved is False
    ask_step, ask_payload = next((item for item in stream.events if item[0] == StepEvent.ask_user))
    notice_step, notice_payload = next((item for item in stream.events if item[0] == StepEvent.notice))
    assert ask_step == StepEvent.ask_user
    assert notice_step == StepEvent.notice
    assert notice_payload["request_id"] == ask_payload["request_id"]
    assert "timed out" in str(notice_payload.get("message", "")).lower()
    assert ask_payload["request_id"] not in task_lock.human_input


@pytest.mark.asyncio
async def test_request_tool_permission_plan_mode_denies_without_prompt() -> None:
    task_lock = TaskLock(project_id="proj-permission-plan")
    stream = _EventStreamStub()

    approved = await _request_tool_permission(
        task_lock=task_lock,
        event_stream=stream,
        toolkit_name="FileToolkitWithEvents",
        method_name="write_to_file",
        message="path='/tmp/report.md'",
        agent_name="developer_agent",
        process_task_id="subtask-plan",
        permission_mode="plan",
    )

    assert approved is False
    ask_events = [payload for step, payload in stream.events if step == StepEvent.ask_user]
    assert ask_events == []
    notice_events = [payload for step, payload in stream.events if step == StepEvent.notice]
    assert notice_events
    assert "plan mode" in str(notice_events[-1].get("message", "")).lower()


@pytest.mark.asyncio
async def test_request_tool_permission_accept_edits_auto_allows_file_write() -> None:
    task_lock = TaskLock(project_id="proj-permission-accept-edits")
    stream = _EventStreamStub()

    approved = await _request_tool_permission(
        task_lock=task_lock,
        event_stream=stream,
        toolkit_name="FileToolkitWithEvents",
        method_name="write_to_file",
        message="path='/tmp/report.md'",
        agent_name="developer_agent",
        process_task_id="subtask-accept-edits",
        permission_mode="acceptEdits",
    )

    assert approved is True
    ask_events = [payload for step, payload in stream.events if step == StepEvent.ask_user]
    assert ask_events == []


@pytest.mark.asyncio
async def test_request_tool_permission_concurrent_requests_keep_responses_isolated() -> None:
    task_lock = TaskLock(project_id="proj-permission-concurrent")
    stream = _EventStreamStub()

    first = asyncio.create_task(
        _request_tool_permission(
            task_lock=task_lock,
            event_stream=stream,
            toolkit_name="TerminalToolkitWithEvents",
            method_name="shell_exec",
            message="command='echo first'",
            agent_name="developer_agent",
            process_task_id="subtask-1",
        )
    )
    second = asyncio.create_task(
        _request_tool_permission(
            task_lock=task_lock,
            event_stream=stream,
            toolkit_name="GmailToolkit",
            method_name="send_email",
            message="to='team@example.com'",
            agent_name="document_agent",
            process_task_id="subtask-2",
        )
    )

    await asyncio.sleep(0)
    ask_events = [payload for step, payload in stream.events if step == StepEvent.ask_user]
    assert len(ask_events) == 2

    request_by_subtask = {
        str(payload["process_task_id"]): str(payload["request_id"])
        for payload in ask_events
    }
    task_lock.human_input[request_by_subtask["subtask-2"]].put_nowait("deny")
    task_lock.human_input[request_by_subtask["subtask-1"]].put_nowait("approve")

    first_result = await first
    second_result = await second

    assert first_result is True
    assert second_result is False


@pytest.mark.asyncio
async def test_request_user_decision_emits_contract_and_returns_response() -> None:
    task_lock = TaskLock(project_id="proj-decision")
    stream = _EventStreamStub()

    pending = asyncio.create_task(
        _request_user_decision(
            task_lock=task_lock,
            event_stream=stream,
            question="What kind of task?",
            options=[
                DecisionOption(id="1", label="Write code"),
                DecisionOption(id="2", label="Plan trip"),
            ],
            mode="single_select",
            process_task_id="subtask-decision",
        )
    )

    await asyncio.sleep(0)
    assert stream.events
    step, payload = next((item for item in stream.events if item[0] == StepEvent.ask_user))
    assert step == StepEvent.ask_user
    assert payload["type"] == "decision"
    assert payload["mode"] == "single_select"
    assert payload["contract_version"] == INTERACTION_CONTRACT_VERSION
    assert len(payload["options"]) == 2

    request_id = str(payload["request_id"])
    task_lock.human_input[request_id].put_nowait("2")
    response = await pending

    assert response == "2"
    assert request_id not in task_lock.human_input
    assert request_id not in task_lock.pending_approval_context


@pytest.mark.asyncio
async def test_request_user_decision_returns_none_on_timeout() -> None:
    task_lock = TaskLock(project_id="proj-decision-timeout")
    stream = _EventStreamStub()

    response = await _request_user_decision(
        task_lock=task_lock,
        event_stream=stream,
        question="Pick one",
        options=[DecisionOption(id="1", label="A")],
        mode="single_select",
        timeout_seconds=0.01,
        process_task_id="subtask-timeout",
    )

    assert response is None
