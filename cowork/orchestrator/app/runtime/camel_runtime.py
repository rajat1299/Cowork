from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Iterable

from camel.agents import ChatAgent
from camel.agents.chat_agent import AsyncStreamingChatAgentResponse
from camel.models import ModelFactory
from camel.societies.workforce.prompts import PROCESS_TASK_PROMPT
from camel.societies.workforce.single_agent_worker import SingleAgentWorker as BaseSingleAgentWorker
from camel.societies.workforce.task_channel import TaskChannel
from camel.societies.workforce.utils import FailureHandlingConfig, TaskAssignResult
from camel.societies.workforce.workforce import (
    DEFAULT_WORKER_POOL_SIZE,
    Workforce as BaseWorkforce,
    WorkforceState,
)
from camel.tasks.task import Task, TaskState

from app.clients.core_api import ProviderConfig, create_history, fetch_configs, fetch_provider, update_history
from app.runtime.actions import ActionType, AgentSpec, TaskStatus
from app.runtime.events import StepEvent
from app.runtime.llm_client import (
    _OPENAI_COMPAT_DEFAULTS,
    _OPENAI_COMPAT_REQUIRES_ENDPOINT,
    _normalize_provider_name,
    collect_chat_completion,
    stream_chat,
)
from app.runtime.sync import fire_and_forget
from app.runtime.task_lock import TaskLock
from app.runtime.tool_context import current_agent_name, current_process_task_id
from app.runtime.toolkits.camel_tools import build_agent_tools
from app.runtime.workforce import (
    AgentProfile,
    build_complexity_prompt,
    build_decomposition_prompt,
    build_default_agents,
    build_results_summary_prompt,
    build_summary_prompt,
    parse_subtasks,
)
from shared.schemas import StepEvent as StepEventModel


def _emit(task_id: str, step: StepEvent, data: dict) -> StepEventModel:
    event = StepEventModel(
        task_id=task_id,
        step=step,
        data=data,
        timestamp=time.time(),
    )
    fire_and_forget(event)
    return event


def _usage_total(usage: dict | None) -> int:
    if not usage:
        return 0
    return int(usage.get("total_tokens") or 0)


def _build_context(task_lock: TaskLock) -> str:
    if not task_lock.conversation_history:
        return ""
    lines = ["=== Previous Conversation ==="]
    for entry in task_lock.conversation_history:
        role = entry.get("role") or "assistant"
        content = entry.get("content") or ""
        if role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) + "\n"


def _parse_summary(summary_text: str) -> tuple[str | None, str | None]:
    if not summary_text:
        return None, None
    if "|" in summary_text:
        name, summary = summary_text.split("|", 1)
        name = name.strip() or None
        summary = summary.strip() or None
        return name, summary
    return None, summary_text.strip()


def _sanitize_identifier(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", value or "")
    return cleaned or fallback


def _resolve_workdir(project_id: str) -> Path:
    base_dir = os.environ.get("COWORK_WORKDIR")
    if base_dir:
        base_path = Path(base_dir).expanduser()
    else:
        base_path = Path.home() / ".cowork" / "workdir"
    safe_project = _sanitize_identifier(project_id, "project")
    workdir = (base_path / safe_project).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


async def _load_tool_env(auth_token: str | None) -> dict[str, str]:
    configs = await fetch_configs(auth_token)
    env_vars: dict[str, str] = {}
    for item in configs:
        key = item.get("key") or item.get("name")
        value = item.get("value")
        if not key or value is None:
            continue
        env_vars[str(key)] = str(value)
    if "MCP_REMOTE_CONFIG_DIR" not in env_vars and "MCP_REMOTE_CONFIG_DIR" not in os.environ:
        env_vars["MCP_REMOTE_CONFIG_DIR"] = str(Path.home() / ".cowork" / "mcp-auth")
    return env_vars


def _apply_env_overrides(overrides: dict[str, str]) -> dict[str, str | None]:
    previous: dict[str, str | None] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _agent_profile_from_spec(spec: AgentSpec) -> AgentProfile:
    name = (spec.name or "").strip()
    description = (spec.description or "").strip()
    system_prompt = (spec.system_prompt or "").strip()
    if not system_prompt:
        if description:
            system_prompt = f"You are {description}"
        else:
            system_prompt = f"You are {name}."
    if not description:
        description = f"{name} agent"
    return AgentProfile(
        name=name,
        description=description,
        system_prompt=system_prompt,
        tools=list(spec.tools or []),
    )


def _merge_agent_specs(
    defaults: list[AgentProfile],
    custom_specs: list[AgentSpec] | None,
) -> list[AgentProfile]:
    if not custom_specs:
        return defaults
    merged = list(defaults)
    for spec in custom_specs:
        name = (spec.name or "").strip()
        if not name:
            continue
        profile = _agent_profile_from_spec(spec)
        replaced = False
        for index, existing in enumerate(merged):
            if existing.name.lower() == name.lower():
                merged[index] = profile
                replaced = True
                break
        if not replaced:
            merged.append(profile)
    return merged


def _resolve_model_url(provider: ProviderConfig) -> str | None:
    if provider.endpoint_url:
        return provider.endpoint_url
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _OPENAI_COMPAT_DEFAULTS:
        return _OPENAI_COMPAT_DEFAULTS[normalized]
    if normalized in _OPENAI_COMPAT_REQUIRES_ENDPOINT:
        raise ValueError("Endpoint URL required for OpenAI-compatible provider")
    return None


async def _is_complex_task(provider: ProviderConfig, question: str, context: str) -> tuple[bool, int]:
    prompt = build_complexity_prompt(question, context)
    messages = [
        {"role": "system", "content": "You are a classifier. Reply only yes or no."},
        {"role": "user", "content": prompt},
    ]
    text, usage = await collect_chat_completion(provider, messages, temperature=0.0)
    normalized = "".join(ch for ch in text.strip().lower() if ch.isalpha())
    if normalized.startswith("no"):
        return False, _usage_total(usage)
    if normalized.startswith("yes"):
        return True, _usage_total(usage)
    return True, _usage_total(usage)


async def _extract_response(response) -> tuple[str, dict | None]:
    if isinstance(response, AsyncStreamingChatAgentResponse):
        content_parts: list[str] = []
        async for chunk in response:
            if chunk.msg and chunk.msg.content:
                content_parts.append(chunk.msg.content)
        final_response = await response
        usage = None
        if hasattr(final_response, "info"):
            usage = final_response.info.get("usage") or final_response.info.get("token_usage")
        return "".join(content_parts).strip(), usage
    content = ""
    if getattr(response, "msg", None):
        content = response.msg.content or ""
    usage = None
    if hasattr(response, "info"):
        usage = response.info.get("usage") or response.info.get("token_usage")
    return content.strip(), usage


def _task_state_value(state: TaskState | str) -> str:
    if hasattr(state, "value"):
        return str(state.value)
    return str(state)


def _find_task(tasks: Iterable[Task], task_id: str) -> Task | None:
    for task in tasks:
        if task.id == task_id:
            return task
        children = getattr(task, "subtasks", None)
        if children:
            found = _find_task(children, task_id)
            if found:
                return found
    return None


@dataclass
class TokenTracker:
    total_tokens: int = 0

    def add(self, usage: dict | None) -> int:
        tokens = _usage_total(usage)
        self.total_tokens += tokens
        return tokens


class EventStream:
    def __init__(self, task_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.task_id = task_id
        self.loop = loop
        self.queue: asyncio.Queue[StepEventModel | None] = asyncio.Queue()

    def emit(self, step: StepEvent, data: dict) -> None:
        event = _emit(self.task_id, step, data)
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.queue.put_nowait, event)
        else:
            self.queue.put_nowait(event)

    def close(self) -> None:
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
        else:
            self.queue.put_nowait(None)

    async def stream(self) -> AsyncIterator[StepEventModel]:
        while True:
            event = await self.queue.get()
            if event is None:
                break
            yield event


class CoworkSingleAgentWorker(BaseSingleAgentWorker):
    def __init__(
        self,
        description: str,
        worker: ChatAgent,
        event_stream: EventStream,
        token_tracker: TokenTracker,
        pool_max_size: int = DEFAULT_WORKER_POOL_SIZE,
    ) -> None:
        self._event_stream = event_stream
        self._token_tracker = token_tracker
        super().__init__(
            description=description,
            worker=worker,
            use_agent_pool=False,
            pool_initial_size=1,
            pool_max_size=pool_max_size,
            auto_scale_pool=False,
            use_structured_output_handler=False,
        )
        self.worker = worker

    async def _process_task(self, task: Task, dependencies: list[Task]) -> TaskState:
        worker_agent = await self._get_worker_agent()
        worker_agent.process_task_id = task.id
        agent_name = getattr(worker_agent, "agent_name", getattr(worker_agent, "role_name", "agent"))
        agent_id = getattr(worker_agent, "agent_id", "")
        task_token = current_process_task_id.set(task.id)
        agent_token = current_agent_name.set(agent_name)
        self._event_stream.emit(
            StepEvent.activate_agent,
            {
                "agent_name": agent_name,
                "process_task_id": task.id,
                "agent_id": agent_id,
                "message": task.content,
            },
        )
        result_text = ""
        tokens = 0
        success = True
        try:
            try:
                dependency_info = self._get_dep_tasks_info(dependencies)
            except Exception:
                dependency_info = "\n".join(f"- {dep.content}" for dep in dependencies) if dependencies else ""
            prompt = PROCESS_TASK_PROMPT.format(
                content=task.content,
                parent_task_content=task.parent.content if getattr(task, "parent", None) else "",
                dependency_tasks_info=dependency_info,
                additional_info=task.additional_info,
            )
            response = await worker_agent.astep(prompt)
            result_text, usage = await _extract_response(response)
            tokens = self._token_tracker.add(usage)
        except Exception as exc:
            result_text = f"Task failed: {exc}"
            success = False
        finally:
            current_process_task_id.reset(task_token)
            current_agent_name.reset(agent_token)
            await self._return_worker_agent(worker_agent)

        self._event_stream.emit(
            StepEvent.deactivate_agent,
            {
                "agent_name": agent_name,
                "process_task_id": task.id,
                "agent_id": agent_id,
                "message": result_text,
                "tokens": tokens,
            },
        )
        task.result = result_text
        if success and result_text:
            task.state = TaskState.DONE
        else:
            task.state = TaskState.FAILED
            task.failure_count += 1
        return task.state


class CoworkWorkforce(BaseWorkforce):
    def __init__(
        self,
        api_task_id: str,
        description: str,
        event_stream: EventStream,
        token_tracker: TokenTracker,
        coordinator_agent: ChatAgent | None = None,
        task_agent: ChatAgent | None = None,
        graceful_shutdown_timeout: float = 3,
        share_memory: bool = False,
    ) -> None:
        self.api_task_id = api_task_id
        self._event_stream = event_stream
        self._token_tracker = token_tracker
        self._node_to_agent_id: dict[str, str] = {}
        super().__init__(
            description=description,
            children=None,
            coordinator_agent=coordinator_agent,
            task_agent=task_agent,
            new_worker_agent=None,
            graceful_shutdown_timeout=graceful_shutdown_timeout,
            share_memory=share_memory,
            use_structured_output_handler=False,
            failure_handling_config=FailureHandlingConfig(enabled_strategies=["retry", "replan"]),
        )
        if getattr(self, "task_agent", None):
            try:
                self.task_agent.stream_accumulate = True
                self.task_agent._stream_accumulate_explicit = True
            except Exception:
                pass

    def add_single_agent_worker(
        self,
        description: str,
        worker: ChatAgent,
        tools: list[str],
        pool_max_size: int = DEFAULT_WORKER_POOL_SIZE,
    ) -> "CoworkWorkforce":
        if self._state == WorkforceState.RUNNING:
            raise RuntimeError("Cannot add workers while workforce is running.")
        if hasattr(self, "_validate_agent_compatibility"):
            try:
                self._validate_agent_compatibility(worker, "Worker agent")
            except Exception:
                pass
        if hasattr(self, "_attach_pause_event_to_agent"):
            try:
                self._attach_pause_event_to_agent(worker)
            except Exception:
                pass

        worker_node = CoworkSingleAgentWorker(
            description=description,
            worker=worker,
            event_stream=self._event_stream,
            token_tracker=self._token_tracker,
            pool_max_size=pool_max_size,
        )
        self._children.append(worker_node)
        if getattr(self, "_channel", None) is not None:
            worker_node.set_channel(self._channel)

        agent_id = getattr(worker, "agent_id", "")
        agent_name = getattr(worker, "agent_name", description)
        node_id = getattr(worker_node, "node_id", None)
        if node_id:
            self._node_to_agent_id[node_id] = agent_id
        self._event_stream.emit(
            StepEvent.create_agent,
            {"agent_name": agent_name, "agent_id": agent_id, "tools": tools},
        )
        return self

    async def start_with_subtasks(self, subtasks: list[Task]) -> None:
        self.set_channel(TaskChannel())
        self._pending_tasks.extendleft(reversed(subtasks))
        await self.start()

    def _get_agent_id_from_node_id(self, node_id: str) -> str | None:
        return self._node_to_agent_id.get(node_id)

    async def _assign_task(self, task: Task, assignee_id: str | None = None) -> list[TaskAssignResult]:
        assigned = await super()._assign_task(task, assignee_id)
        for item in assigned:
            if self._task and item.task_id == self._task.id:
                continue
            task_obj = _find_task(self._task.subtasks if self._task else [], item.task_id)
            content = task_obj.content if task_obj else ""
            agent_id = self._get_agent_id_from_node_id(item.assignee_id)
            if not agent_id:
                continue
            self._event_stream.emit(
                StepEvent.assign_task,
                {
                    "assignee_id": agent_id,
                    "task_id": item.task_id,
                    "content": content,
                    "state": "waiting",
                    "failure_count": task_obj.failure_count if task_obj else 0,
                },
            )
        return assigned

    async def _post_task(self, task: Task, assignee_id: str) -> None:
        if self._task and task.id != self._task.id:
            agent_id = self._get_agent_id_from_node_id(assignee_id)
            if agent_id:
                self._event_stream.emit(
                    StepEvent.assign_task,
                    {
                        "assignee_id": agent_id,
                        "task_id": task.id,
                        "content": task.content,
                        "state": "running",
                        "failure_count": task.failure_count,
                    },
                )
        await super()._post_task(task, assignee_id)

    async def _handle_completed_task(self, task: Task) -> None:
        self._event_stream.emit(
            StepEvent.task_state,
            {
                "task_id": task.id,
                "content": task.content,
                "state": _task_state_value(task.state),
                "result": task.result or "",
                "failure_count": task.failure_count,
            },
        )
        await super()._handle_completed_task(task)

    async def _handle_failed_task(self, task: Task) -> bool:
        result = await super()._handle_failed_task(task)
        self._event_stream.emit(
            StepEvent.task_state,
            {
                "task_id": task.id,
                "content": task.content,
                "state": _task_state_value(task.state),
                "result": task.result or "",
                "failure_count": task.failure_count,
            },
        )
        return result

    def stop_gracefully(self) -> None:
        stop_fn = getattr(super(), "stop_gracefully", None)
        if callable(stop_fn):
            stop_fn()
        else:
            super().stop()


def _build_agent(
    provider: ProviderConfig,
    system_prompt: str,
    agent_id: str,
    stream: bool = False,
    tools: list | None = None,
) -> ChatAgent:
    model_config = {"stream": True} if stream else None
    model = ModelFactory.create(
        model_platform=provider.provider_name,
        model_type=provider.model_type,
        api_key=provider.api_key,
        url=_resolve_model_url(provider),
        timeout=60,
        model_config_dict=model_config,
    )
    agent = ChatAgent(system_message=system_prompt, model=model, agent_id=agent_id, tools=tools)
    return agent


async def _run_camel_complex(
    task_lock: TaskLock,
    action,
    provider: ProviderConfig,
    history_id: int | None,
    token_tracker: TokenTracker,
    event_stream: EventStream,
    context: str,
) -> None:
    env_snapshot: dict[str, str | None] | None = None
    try:
        decompose_parts: list[str] = []
        decompose_usage: dict | None = None
        decompose_prompt = build_decomposition_prompt(action.question, context)
        decompose_messages = [
            {"role": "system", "content": "You are a task planner."},
            {"role": "user", "content": decompose_prompt},
        ]
        try:
            async for chunk, usage_update in stream_chat(provider, decompose_messages):
                if task_lock.stop_requested:
                    break
                if chunk:
                    decompose_parts.append(chunk)
                    event_stream.emit(
                        StepEvent.decompose_text,
                        {
                            "project_id": action.project_id,
                            "task_id": action.task_id,
                            "content": chunk,
                        },
                    )
                if usage_update:
                    decompose_usage = usage_update
        except Exception as exc:
            event_stream.emit(StepEvent.error, {"error": str(exc)})
            event_stream.emit(
                StepEvent.end,
                {"result": "error", "reason": "Decomposition failed"},
            )
            if history_id is not None:
                await update_history(action.auth_token, history_id, {"status": 3})
            task_lock.status = TaskStatus.done
            return

        token_tracker.add(decompose_usage)

        if task_lock.stop_requested:
            event_stream.emit(
                StepEvent.end,
                {"result": "stopped", "reason": "user_stop"},
            )
            if history_id is not None:
                await update_history(action.auth_token, history_id, {"status": 3})
            task_lock.status = TaskStatus.stopped
            return

        raw_decomposition = "".join(decompose_parts).strip()
        task_nodes = parse_subtasks(raw_decomposition, action.task_id)

        summary_prompt = build_summary_prompt(action.question, task_nodes)
        summary_text, summary_usage = await collect_chat_completion(
            provider,
            [
                {"role": "system", "content": "You summarize tasks."},
                {"role": "user", "content": summary_prompt},
            ],
            temperature=0.2,
        )
        token_tracker.add(summary_usage)
        project_name, summary = _parse_summary(summary_text)

        payload = {
            "project_id": action.project_id,
            "task_id": action.task_id,
            "sub_tasks": [task.to_dict() for task in task_nodes],
            "delta_sub_tasks": [task.to_dict() for task in task_nodes],
            "is_final": True,
            "summary_task": summary_text or summary or "",
        }
        event_stream.emit(StepEvent.to_sub_tasks, payload)

        workdir = _resolve_workdir(action.project_id)
        tool_env = await _load_tool_env(action.auth_token)
        tool_env["CAMEL_WORKDIR"] = str(workdir)
        env_snapshot = _apply_env_overrides(tool_env)

        coordinator_agent = _build_agent(
            provider,
            "You are a coordinating agent that helps route work to specialists.",
            str(uuid.uuid4()),
        )
        coordinator_agent.agent_name = "coordinator_agent"
        task_agent = _build_agent(
            provider,
            "You are a task planning agent that decomposes complex work.",
            str(uuid.uuid4()),
            stream=True,
        )
        task_agent.agent_name = "task_agent"

        workforce = CoworkWorkforce(
            action.task_id,
            "Cowork workforce",
            event_stream,
            token_tracker,
            coordinator_agent=coordinator_agent,
            task_agent=task_agent,
        )
        task_lock.workforce = workforce

        agent_specs = _merge_agent_specs(build_default_agents(), action.agents)
        for spec in agent_specs:
            tools = build_agent_tools(spec.tools or [], event_stream, spec.name, str(workdir))
            agent = _build_agent(provider, spec.system_prompt, spec.agent_id, tools=tools)
            agent.agent_name = spec.name
            workforce.add_single_agent_worker(spec.description, agent, spec.tools)

        main_task = Task(content=action.question, id=action.task_id)
        camel_subtasks: list[Task] = []
        for node in task_nodes:
            task = Task(content=node.content, id=node.id)
            task.parent = main_task
            camel_subtasks.append(task)
            node.result = ""
        main_task.subtasks = camel_subtasks
        workforce._task = main_task

        run_task = asyncio.create_task(workforce.start_with_subtasks(camel_subtasks))
        task_lock.add_background_task(run_task)
        while not run_task.done():
            if task_lock.stop_requested:
                workforce.stop_gracefully()
                break
            await asyncio.sleep(0.5)
        await run_task

        if task_lock.stop_requested:
            event_stream.emit(
                StepEvent.end,
                {"result": "stopped", "reason": "user_stop"},
            )
            if history_id is not None:
                await update_history(action.auth_token, history_id, {"status": 3})
            task_lock.status = TaskStatus.stopped
            return

        node_lookup = {node.id: node for node in task_nodes}
        for subtask in camel_subtasks:
            if subtask.id in node_lookup:
                node_lookup[subtask.id].result = subtask.result or ""

        final_result = "\n".join(
            f"- {task.content}\n  {task.result}" for task in camel_subtasks if task.result
        ).strip()
        if len(camel_subtasks) > 1:
            results_prompt = build_results_summary_prompt(action.question, task_nodes)
            summary_result, results_usage = await collect_chat_completion(
                provider,
                [
                    {"role": "system", "content": "You summarize results."},
                    {"role": "user", "content": results_prompt},
                ],
                temperature=0.2,
            )
            token_tracker.add(results_usage)
            if summary_result:
                final_result = summary_result

        if not final_result:
            final_result = "Task completed."

        if history_id is not None:
            await update_history(
                action.auth_token,
                history_id,
                {
                    "tokens": token_tracker.total_tokens,
                    "status": 2,
                    "summary": summary,
                    "project_name": project_name,
                },
            )

        event_stream.emit(StepEvent.end, {"result": final_result})
        task_lock.add_conversation("task_result", final_result)
        task_lock.status = TaskStatus.done
    except Exception as exc:
        event_stream.emit(StepEvent.error, {"error": str(exc)})
        event_stream.emit(
            StepEvent.end,
            {"result": "error", "reason": "Workforce execution failed"},
        )
        if history_id is not None:
            await update_history(action.auth_token, history_id, {"status": 3})
        task_lock.status = TaskStatus.done
    finally:
        if env_snapshot is not None:
            _restore_env(env_snapshot)
        task_lock.workforce = None
        event_stream.close()


async def run_task_loop(task_lock: TaskLock) -> AsyncIterator[StepEventModel]:
    while True:
        try:
            action = await task_lock.get()
        except asyncio.CancelledError:
            break

        if action.type == ActionType.improve:
            task_lock.stop_requested = False
            task_lock.status = TaskStatus.processing
            task_lock.current_task_id = action.task_id

            yield _emit(action.task_id, StepEvent.confirmed, {"question": action.question})
            yield _emit(action.task_id, StepEvent.task_state, {"state": "processing"})

            provider: ProviderConfig | None = None
            if action.api_key and action.model_type:
                provider = ProviderConfig(
                    id=0,
                    provider_name=action.model_provider or "custom",
                    model_type=action.model_type,
                    api_key=action.api_key,
                    endpoint_url=action.endpoint_url,
                    prefer=True,
                )
            if not provider:
                provider = await fetch_provider(
                    action.auth_token,
                    action.provider_id,
                    action.model_provider,
                    action.model_type,
                )

            if not provider or not provider.api_key or not provider.model_type:
                yield _emit(action.task_id, StepEvent.error, {"error": "No provider configured"})
                yield _emit(
                    action.task_id,
                    StepEvent.end,
                    {"result": "error", "reason": "No provider configured"},
                )
                task_lock.status = TaskStatus.done
                continue

            history_id = None
            history_payload = {
                "task_id": action.task_id,
                "project_id": action.project_id,
                "question": action.question,
                "language": "en",
                "model_platform": provider.provider_name,
                "model_type": provider.model_type,
                "status": 1,
            }
            history = await create_history(action.auth_token, history_payload)
            if history:
                history_id = history.get("id")

            total_tokens = 0
            context = _build_context(task_lock)
            is_complex, complexity_tokens = await _is_complex_task(provider, action.question, context)
            total_tokens += complexity_tokens

            if not is_complex:
                content_parts: list[str] = []
                usage: dict | None = None
                try:
                    messages = [{"role": "user", "content": action.question}]
                    async for chunk, usage_update in stream_chat(provider, messages):
                        if task_lock.stop_requested:
                            break
                        if chunk:
                            content_parts.append(chunk)
                            yield _emit(action.task_id, StepEvent.streaming, {"chunk": chunk})
                        if usage_update:
                            usage = usage_update
                except Exception as exc:
                    yield _emit(action.task_id, StepEvent.error, {"error": str(exc)})
                    yield _emit(
                        action.task_id,
                        StepEvent.end,
                        {"result": "error", "reason": "Model call failed"},
                    )
                    if history_id is not None:
                        await update_history(action.auth_token, history_id, {"status": 3})
                    task_lock.status = TaskStatus.done
                    continue

                if task_lock.stop_requested:
                    yield _emit(
                        action.task_id,
                        StepEvent.end,
                        {"result": "stopped", "reason": "user_stop"},
                    )
                    if history_id is not None:
                        await update_history(action.auth_token, history_id, {"status": 3})
                    task_lock.status = TaskStatus.stopped
                    continue

                result_text = "".join(content_parts).strip()
                total_tokens += _usage_total(usage)
                if history_id is not None:
                    await update_history(action.auth_token, history_id, {"tokens": total_tokens, "status": 2})

                yield _emit(action.task_id, StepEvent.end, {"result": result_text, "usage": usage or {}})
                task_lock.add_conversation("assistant", result_text)
                task_lock.status = TaskStatus.done
                continue

            loop = asyncio.get_running_loop()
            event_stream = EventStream(action.task_id, loop)
            token_tracker = TokenTracker(total_tokens)
            run_task = asyncio.create_task(
                _run_camel_complex(
                    task_lock,
                    action,
                    provider,
                    history_id,
                    token_tracker,
                    event_stream,
                    context,
                )
            )
            task_lock.add_background_task(run_task)
            async for event in event_stream.stream():
                yield event
            continue

        if action.type == ActionType.stop:
            if task_lock.workforce:
                try:
                    task_lock.workforce.stop_gracefully()
                except Exception:
                    pass
            task_lock.status = TaskStatus.stopped
            yield _emit(
                task_lock.current_task_id or "unknown",
                StepEvent.end,
                {"result": "stopped", "reason": action.reason},
            )
            break
