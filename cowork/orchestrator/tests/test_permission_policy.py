from __future__ import annotations

import asyncio

import pytest

from app.runtime.config_helpers import (
    _human_readable_permission,
    _request_tool_permission,
    _tool_approval_tier,
)
from app.runtime.events import StepEvent
from app.runtime.task_lock import TaskLock


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
    step, payload = stream.events[0]
    assert step == StepEvent.ask_user
    assert payload["tier"] == "ask_once"
    assert payload["human_question"]
    assert payload["detail"]
    assert payload["question"] == payload["human_question"]

    request_id = payload["request_id"]
    assert request_id in task_lock.pending_approval_context
    response_queue = task_lock.human_input[request_id]
    response_queue.put_nowait("approve")

    approved = await pending
    assert approved is True
    assert task_lock.remembered_approvals == set()
    assert request_id not in task_lock.pending_approval_context


@pytest.mark.asyncio
async def test_request_tool_permission_skips_ask_once_when_toolkit_already_remembered() -> None:
    task_lock = TaskLock(
        project_id="proj-permission",
        remembered_approvals={"filetoolkitwithevents"},
    )
    stream = _EventStreamStub()

    approved = await _request_tool_permission(
        task_lock=task_lock,
        event_stream=stream,
        toolkit_name="FileToolkitWithEvents",
        method_name="write_to_file",
        message="path='/tmp/report.md'",
        agent_name="document_agent",
        process_task_id="subtask-1",
    )

    assert approved is True
    assert stream.events == []
