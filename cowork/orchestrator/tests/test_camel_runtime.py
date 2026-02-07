import asyncio
import types
from pathlib import Path

import pytest
from camel.tasks.task import TaskState

from app.clients.core_api import ProviderConfig
from app.runtime import camel_runtime as cr
from app.runtime.actions import ActionImprove
from app.runtime.events import StepEvent
from app.runtime.task_lock import TaskLock
from app.runtime.tool_context import current_project_id


@pytest.mark.asyncio
async def test_event_stream_round_trip():
    loop = asyncio.get_running_loop()
    stream = cr.EventStream("task-1", loop)
    stream.emit(StepEvent.confirmed, {"question": "hello"})
    stream.emit(StepEvent.end, {"result": "done"})
    stream.close()

    events = [event async for event in stream.stream()]
    steps = [event.step for event in events]

    assert steps == [StepEvent.confirmed.value, StepEvent.end.value]


@pytest.mark.asyncio
async def test_event_stream_emits_artifact_after_tool_deactivation(monkeypatch, tmp_path: Path):
    loop = asyncio.get_running_loop()
    stream = cr.EventStream("task-artifact-stream", loop)

    project_token = current_project_id.set("proj-artifact-stream")
    monkeypatch.setenv("CAMEL_WORKDIR", str(tmp_path))
    monkeypatch.setattr(cr, "fire_and_forget", lambda event: None)
    monkeypatch.setattr(cr, "fire_and_forget_artifact", lambda event: None)

    output_path = tmp_path / "outputs" / "summary.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("artifact content", encoding="utf-8")

    try:
        cr._cleanup_artifact_cache("task-artifact-stream")
        stream.emit(
            StepEvent.deactivate_toolkit,
            {
                "agent_name": "document_agent",
                "process_task_id": "step-1",
                "toolkit_name": "FileToolkitWithEvents",
                "method_name": "write to file",
                "message": f"Content successfully written to file: {output_path}",
            },
        )
        stream.close()
        events = [event async for event in stream.stream()]
    finally:
        current_project_id.reset(project_token)

    assert [event.step for event in events] == [
        StepEvent.deactivate_toolkit.value,
        StepEvent.artifact.value,
    ]
    artifact_data = events[1].data
    assert artifact_data["name"] == "summary.md"
    assert str(artifact_data["content_url"]).startswith(
        "/files/generated/proj-artifact-stream/download?path="
    )


@pytest.mark.asyncio
async def test_camel_complex_flow_emits_expected_steps(monkeypatch):
    async def fake_is_complex(provider, question, context):
        return True, 1

    async def fake_stream_chat(provider, messages, temperature=0.2, extra_params=None):
        payload = '[{"id":"t1","content":"First task"},{"id":"t2","content":"Second task"}]'
        yield payload, {"total_tokens": 2}

    call_index = {"count": 0}

    async def fake_collect(provider, messages, temperature=0.2, on_chunk=None, extra_params=None):
        call_index["count"] += 1
        if call_index["count"] == 1:
            return "Demo|Summary", {"total_tokens": 5}
        return "All done", {"total_tokens": 7}

    async def fake_create_history(auth_header, payload):
        return {"id": 10}

    async def fake_update_history(auth_header, history_id, payload):
        updates.append(payload)

    async def fake_fetch_configs(auth_header, group=None):
        return []

    async def fake_fetch_mcp_users(auth_header):
        return []

    def fake_build_agent(provider, system_prompt, agent_id, stream=False, tools=None, extra_params=None):
        return types.SimpleNamespace(agent_id=agent_id, agent_name="agent")

    class FakeWorkforce:
        def __init__(
            self,
            api_task_id,
            description,
            event_stream,
            token_tracker,
            coordinator_agent=None,
            task_agent=None,
            graceful_shutdown_timeout=3,
            share_memory=False,
        ):
            self._event_stream = event_stream
            self._agent_ids = []
            self._agent_names = []
            self._task = None

        def add_single_agent_worker(self, description, worker, tools, pool_max_size=1):
            agent_id = getattr(worker, "agent_id", f"agent-{len(self._agent_ids) + 1}")
            agent_name = getattr(worker, "agent_name", description)
            self._agent_ids.append(agent_id)
            self._agent_names.append(agent_name)
            self._event_stream.emit(
                StepEvent.create_agent,
                {"agent_name": agent_name, "agent_id": agent_id, "tools": tools},
            )
            return self

        async def start_with_subtasks(self, subtasks):
            agent_id = self._agent_ids[0] if self._agent_ids else "agent-1"
            agent_name = self._agent_names[0] if self._agent_names else "agent"
            for task in subtasks:
                failure_count = getattr(task, "failure_count", 0)
                self._event_stream.emit(
                    StepEvent.assign_task,
                    {
                        "assignee_id": agent_id,
                        "task_id": task.id,
                        "content": task.content,
                        "state": "waiting",
                        "failure_count": failure_count,
                    },
                )
                self._event_stream.emit(
                    StepEvent.assign_task,
                    {
                        "assignee_id": agent_id,
                        "task_id": task.id,
                        "content": task.content,
                        "state": "running",
                        "failure_count": failure_count,
                    },
                )
                self._event_stream.emit(
                    StepEvent.activate_agent,
                    {
                        "agent_name": agent_name,
                        "process_task_id": task.id,
                        "agent_id": agent_id,
                        "message": task.content,
                    },
                )
                task.result = f"Result for {task.content}"
                task.state = TaskState.DONE
                self._event_stream.emit(
                    StepEvent.deactivate_agent,
                    {
                        "agent_name": agent_name,
                        "process_task_id": task.id,
                        "agent_id": agent_id,
                        "message": task.result,
                        "tokens": 3,
                    },
                )
                self._event_stream.emit(
                    StepEvent.task_state,
                    {
                        "task_id": task.id,
                        "content": task.content,
                        "state": task.state.value,
                        "result": task.result,
                        "failure_count": failure_count,
                    },
                )

        def stop_gracefully(self):
            return None

    updates = []
    monkeypatch.setattr(cr, "_is_complex_task", fake_is_complex)
    monkeypatch.setattr(cr, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(cr, "collect_chat_completion", fake_collect)
    monkeypatch.setattr(cr, "create_history", fake_create_history)
    monkeypatch.setattr(cr, "update_history", fake_update_history)
    monkeypatch.setattr(cr, "fetch_configs", fake_fetch_configs)
    monkeypatch.setattr(cr, "fetch_mcp_users", fake_fetch_mcp_users)
    monkeypatch.setattr(cr, "build_agent_tools", lambda *args, **kwargs: [])
    monkeypatch.setattr(cr, "_build_agent", fake_build_agent)
    monkeypatch.setattr(cr, "CoworkWorkforce", FakeWorkforce)
    monkeypatch.setattr(cr, "fire_and_forget", lambda event: None)

    task_lock = TaskLock(project_id="proj-1")
    await task_lock.put(
        ActionImprove(
            project_id="proj-1",
            task_id="task-1",
            question="Plan a small feature with steps",
            auth_token="Bearer test",
            model_provider="openrouter",
            model_type="deepseek/deepseek-v3.2",
            api_key="test-key",
            endpoint_url="https://openrouter.ai/api/v1",
        )
    )

    events = []
    async for event in cr.run_task_loop(task_lock):
        events.append(event)
        if event.step == StepEvent.end.value:
            break

    steps = [event.step for event in events]

    assert steps[0] == StepEvent.confirmed.value
    assert steps[1] == StepEvent.task_state.value
    assert StepEvent.decompose_text.value in steps
    assert StepEvent.to_sub_tasks.value in steps
    assert StepEvent.create_agent.value in steps
    assert StepEvent.assign_task.value in steps
    assert StepEvent.activate_agent.value in steps
    assert StepEvent.deactivate_agent.value in steps
    assert StepEvent.task_state.value in steps
    assert steps[-1] == StepEvent.end.value
    assert updates and any("tokens" in payload for payload in updates)


def test_extract_file_artifact_from_write_file_result(monkeypatch, tmp_path: Path):
    task_id = "task-artifact-file"
    project_ctx = current_project_id.set("proj-artifacts")
    try:
        monkeypatch.setenv("CAMEL_WORKDIR", str(tmp_path))

        captured_events = []
        monkeypatch.setattr(cr, "fire_and_forget_artifact", lambda event: captured_events.append(event))

        output_path = tmp_path / "outputs" / "summary.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("hello", encoding="utf-8")

        cr._cleanup_artifact_cache(task_id)
        payloads = cr._extract_file_artifacts(
            task_id,
            {"message": f"Content successfully written to file: {output_path}"},
        )

        assert len(payloads) == 1
        payload = payloads[0]
        assert payload["name"] == "summary.md"
        assert payload["type"] == "file"
        assert payload["path"] == str(output_path)
        assert payload["content_url"].startswith("/files/generated/proj-artifacts/download?path=")
        assert captured_events and captured_events[0].name == "summary.md"

        duplicate = cr._extract_file_artifacts(
            task_id,
            {"message": f"Content successfully written to file: {output_path}"},
        )
        assert duplicate == []
    finally:
        current_project_id.reset(project_ctx)


def test_collect_tool_artifacts_skips_large_raw_tool_output(monkeypatch, tmp_path: Path):
    task_id = "task-skip-tool-output"
    monkeypatch.setenv("CAMEL_WORKDIR", str(tmp_path))
    captured_events = []
    monkeypatch.setattr(cr, "fire_and_forget_artifact", lambda event: captured_events.append(event))

    cr._cleanup_artifact_cache(task_id)
    payloads = cr._collect_tool_artifacts(task_id, {"message": "x" * 10000})

    assert payloads == []
    assert captured_events == []


def test_build_generated_file_url_infers_project_id_from_workdir_path(tmp_path: Path):
    workdir = tmp_path / ".cowork" / "workdir" / "project-123"
    workdir.mkdir(parents=True, exist_ok=True)
    output_path = workdir / "reports" / "summary.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("hello", encoding="utf-8")

    project_ctx = current_project_id.set(None)
    try:
        url = cr._build_generated_file_url(workdir, output_path)
    finally:
        current_project_id.reset(project_ctx)

    assert url == "/files/generated/project-123/download?path=reports/summary.md"


def test_runtime_skills_force_complex_and_upgrade_tools():
    question = "Create a detailed .xlsx spreadsheet with formulas and save it as an output file"
    active_skills = cr.detect_runtime_skills(question, attachments=None)

    assert any(skill.name == "xlsx" for skill in active_skills)
    assert cr.requires_complex_execution(question, active_skills) is True

    agent_specs = cr._merge_agent_specs(cr.build_default_agents(), None)
    cr.apply_runtime_skills(agent_specs, active_skills)
    document_agent = next(agent for agent in agent_specs if agent.name == "document_agent")

    assert "excel" in document_agent.tools
    assert "terminal" in document_agent.tools
