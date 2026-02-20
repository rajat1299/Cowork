from __future__ import annotations

from typing import Any, Iterable

from camel.agents import ChatAgent
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

from app.clients.core_api import ProviderConfig
from app.runtime.camel_agent import CoworkChatAgent
from app.runtime.events import StepEvent
from app.runtime.streaming import EventStream, TokenTracker
from app.runtime.task_analysis import _extract_response, _resolve_model_url
from app.runtime.tool_context import current_agent_name, current_process_task_id


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
    extra_params: dict[str, Any] | None = None,
) -> ChatAgent:
    model_config: dict[str, Any] = {}
    if stream:
        model_config["stream"] = True
    encrypted_config = provider.encrypted_config if isinstance(provider.encrypted_config, dict) else {}
    if encrypted_config:
        extra_params = encrypted_config.get("extra_params")
        if isinstance(extra_params, dict):
            model_config.update(extra_params)
        else:
            model_config.update(encrypted_config)
    if not model_config:
        model_config = None
    if extra_params:
        if model_config is None:
            model_config = {}
        model_config.update(extra_params)
    model = ModelFactory.create(
        model_platform=provider.provider_name,
        model_type=provider.model_type,
        api_key=provider.api_key,
        url=_resolve_model_url(provider),
        timeout=60,
        model_config_dict=model_config,
    )
    agent = CoworkChatAgent(system_message=system_prompt, model=model, agent_id=agent_id, tools=tools)
    return agent
