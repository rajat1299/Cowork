import asyncio
import time
from typing import AsyncIterator

from app.clients.core_api import ProviderConfig, create_history, fetch_provider, update_history
from app.runtime.actions import ActionType, TaskStatus
from app.runtime.events import StepEvent
from app.runtime.llm_client import collect_chat_completion, stream_chat
from app.runtime.sync import fire_and_forget
from app.runtime.task_lock import TaskLock
from app.runtime.workforce import (
    build_complexity_prompt,
    build_decomposition_prompt,
    build_default_agents,
    build_results_summary_prompt,
    build_subtask_prompt,
    build_summary_prompt,
    parse_subtasks,
    pick_agent,
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

            agents = build_default_agents()
            for agent in agents:
                yield _emit(
                    action.task_id,
                    StepEvent.create_agent,
                    {"agent_name": agent.name, "agent_id": agent.agent_id, "tools": agent.tools},
                )

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
                        yield _emit(
                            action.task_id,
                            StepEvent.decompose_text,
                            {"project_id": action.project_id, "task_id": action.task_id, "content": chunk},
                        )
                    if usage_update:
                        decompose_usage = usage_update
            except Exception as exc:
                yield _emit(action.task_id, StepEvent.error, {"error": str(exc)})
                yield _emit(
                    action.task_id,
                    StepEvent.end,
                    {"result": "error", "reason": "Decomposition failed"},
                )
                if history_id is not None:
                    await update_history(action.auth_token, history_id, {"status": 3})
                task_lock.status = TaskStatus.done
                continue

            total_tokens += _usage_total(decompose_usage)

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

            raw_decomposition = "".join(decompose_parts).strip()
            subtasks = parse_subtasks(raw_decomposition, action.task_id)

            summary_prompt = build_summary_prompt(action.question, subtasks)
            summary_text, summary_usage = await collect_chat_completion(
                provider,
                [
                    {"role": "system", "content": "You summarize tasks."},
                    {"role": "user", "content": summary_prompt},
                ],
                temperature=0.2,
            )
            total_tokens += _usage_total(summary_usage)
            project_name, summary = _parse_summary(summary_text)

            payload = {
                "project_id": action.project_id,
                "task_id": action.task_id,
                "sub_tasks": [task.to_dict() for task in subtasks],
                "delta_sub_tasks": [task.to_dict() for task in subtasks],
                "is_final": True,
                "summary_task": summary_text or summary or "",
            }
            yield _emit(action.task_id, StepEvent.to_sub_tasks, payload)

            for task in subtasks:
                if task_lock.stop_requested:
                    break
                agent = pick_agent(task.content, agents)
                task.assignee_id = agent.agent_id

                yield _emit(
                    action.task_id,
                    StepEvent.assign_task,
                    {
                        "assignee_id": agent.agent_id,
                        "task_id": task.id,
                        "content": task.content,
                        "state": "waiting",
                        "failure_count": task.failure_count,
                    },
                )
                yield _emit(
                    action.task_id,
                    StepEvent.assign_task,
                    {
                        "assignee_id": agent.agent_id,
                        "task_id": task.id,
                        "content": task.content,
                        "state": "running",
                        "failure_count": task.failure_count,
                    },
                )
                yield _emit(
                    action.task_id,
                    StepEvent.activate_agent,
                    {
                        "agent_name": agent.name,
                        "process_task_id": task.id,
                        "agent_id": agent.agent_id,
                        "message": task.content,
                    },
                )

                subtask_prompt = build_subtask_prompt(action.question, task, agent, context)
                result_text, result_usage = await collect_chat_completion(
                    provider,
                    [
                        {"role": "system", "content": agent.system_prompt},
                        {"role": "user", "content": subtask_prompt},
                    ],
                    temperature=0.2,
                )
                total_tokens += _usage_total(result_usage)

                task.result = result_text
                task.state = "DONE" if result_text else "FAILED"
                if not result_text:
                    task.failure_count += 1

                yield _emit(
                    action.task_id,
                    StepEvent.deactivate_agent,
                    {
                        "agent_name": agent.name,
                        "process_task_id": task.id,
                        "agent_id": agent.agent_id,
                        "message": result_text,
                        "tokens": _usage_total(result_usage),
                    },
                )
                yield _emit(
                    action.task_id,
                    StepEvent.task_state,
                    {
                        "task_id": task.id,
                        "content": task.content,
                        "state": task.state,
                        "result": task.result,
                        "failure_count": task.failure_count,
                    },
                )

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

            final_result = "\n".join(
                f"- {task.content}\n  {task.result}" for task in subtasks if task.result
            ).strip()
            if len(subtasks) > 1:
                results_prompt = build_results_summary_prompt(action.question, subtasks)
                summary_result, results_usage = await collect_chat_completion(
                    provider,
                    [
                        {"role": "system", "content": "You summarize results."},
                        {"role": "user", "content": results_prompt},
                    ],
                    temperature=0.2,
                )
                total_tokens += _usage_total(results_usage)
                if summary_result:
                    final_result = summary_result

            if not final_result:
                final_result = "Task completed."

            if history_id is not None:
                await update_history(
                    action.auth_token,
                    history_id,
                    {
                        "tokens": total_tokens,
                        "status": 2,
                        "summary": summary,
                        "project_name": project_name,
                    },
                )

            yield _emit(action.task_id, StepEvent.end, {"result": final_result})
            task_lock.add_conversation("task_result", final_result)
            task_lock.status = TaskStatus.done
            continue

        if action.type == ActionType.stop:
            task_lock.status = TaskStatus.stopped
            yield _emit(
                task_lock.current_task_id or "unknown",
                StepEvent.end,
                {"result": "stopped", "reason": action.reason},
            )
            break
