from __future__ import annotations

import asyncio
import platform
import uuid
from datetime import datetime, timezone
from typing import Any

from camel.toolkits.mcp_toolkit import MCPToolkit
from camel.tasks.task import Task

from app.clients.core_api import ProviderConfig, update_history, upsert_task_summary
from app.runtime.actions import TaskStatus
from app.runtime.agents import CoworkWorkforce, _build_agent
from app.runtime.config_helpers import (
    _apply_env_overrides,
    _env_flag,
    _request_tool_permission,
    _restore_env,
)
from app.runtime.context import _load_tool_env, _parse_summary, _resolve_workdir
from app.runtime.events import StepEvent
from app.runtime.memory import _generate_global_memory_notes, _persist_message
from app.runtime.mcp_config import _load_mcp_tools
from app.runtime.skill_engine import SkillRunState, get_runtime_skill_engine
from app.runtime.skills import RuntimeSkill, apply_runtime_skills, build_runtime_skill_context
from app.runtime.streaming import EventStream, TokenTracker
from app.runtime.task_analysis import _ensure_tool, _merge_agent_specs, _strip_search_tools
from app.runtime.task_lock import TaskLock
from app.runtime.toolkits.camel_tools import build_agent_tools
from app.runtime.tracing import _trace_log
from app.runtime.workforce import (
    build_default_agents,
    build_decomposition_prompt,
    build_results_summary_prompt,
    build_summary_prompt,
    parse_subtasks,
)
from app.runtime.llm_client import collect_chat_completion, stream_chat


def _build_global_base_context(working_directory: str, project_name: str) -> str:
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""<operating_environment>
- **System**: {os_info}
- **Working Directory**: `{working_directory}`.
  - ALL file operations must happen inside this directory.
  - Use absolute paths for precision.
- **Date**: {current_date}
</operating_environment>

<memory_protocol>
- **User Context**: You have access to `GLOBAL_USER_CONTEXT`. Respect the user's stated preferences (tech stack, tone, workflow) found there.
- **Project Context**: You are working within project `{project_name}`.
</memory_protocol>

<execution_philosophy>
- **Bias for Action**: Do not just suggest code; write it. Do not just suggest a search; perform it.
- **Artifacts over Chat**: Whenever possible, produce tangible outputs (files, code, reports) rather than just long chat messages.
- **Tool Discipline**: Never guess tool parameters. If a path or ID is missing, verify it first using `ls` or `search`.
</execution_philosophy>

"""


async def _run_camel_complex(
    task_lock: TaskLock,
    action,
    provider: ProviderConfig,
    extra_params: dict[str, Any] | None,
    search_enabled: bool,
    native_search_enabled: bool,
    history_id: int | None,
    token_tracker: TokenTracker,
    event_stream: EventStream,
    context: str,
    memory_generate_enabled: bool,
    active_skills: list[RuntimeSkill],
    skill_run_state: SkillRunState | None,
) -> None:
    env_snapshot: dict[str, str | None] | None = None
    mcp_toolkit: MCPToolkit | None = None
    skill_engine = get_runtime_skill_engine()
    try:
        if skill_run_state and skill_run_state.active_skills:
            if skill_run_state.query_plan:
                event_stream.emit(
                    StepEvent.notice,
                    {
                        "message": "Prepared research query plan.",
                        "skill_id": skill_run_state.active_skills[0].id,
                        "skill_version": skill_run_state.active_skills[0].version,
                        "skill_stage": "prepare_plan",
                        "skill_checkpoint": "query_plan_ready",
                        "query_plan": skill_run_state.query_plan,
                    },
                )
            _trace_log(
                "skill_stage",
                {
                    "task_id": action.task_id,
                    "stage": "prepare_plan",
                    "skills": [skill.id for skill in skill_run_state.active_skills],
                },
            )
        decompose_parts: list[str] = []
        decompose_usage: dict | None = None
        decompose_prompt = build_decomposition_prompt(action.question, context)
        decompose_messages = [
            {"role": "system", "content": "You are a task planner. Return only valid JSON."},
            {"role": "user", "content": decompose_prompt},
        ]
        try:
            async for chunk, usage_update in stream_chat(
                provider,
                decompose_messages,
                extra_params=extra_params,
            ):
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
            event_stream.emit(StepEvent.turn_cancelled, {"reason": "user_stop"})
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
            extra_params=extra_params,
        )
        token_tracker.add(summary_usage)
        project_name, summary = _parse_summary(summary_text)
        task_summary = summary or summary_text or ""
        if task_summary:
            task_lock.last_task_summary = task_summary
            await upsert_task_summary(
                action.auth_token,
                action.task_id,
                task_summary,
                project_id=action.project_id,
            )

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
        mcp_toolkit, mcp_tools = await _load_mcp_tools(action.auth_token)
        memory_search_enabled = _env_flag("MEMORY_SEARCH_PAST_CHATS", default=True)

        coordinator_agent = _build_agent(
            provider,
            "You are a coordinating agent that routes work to specialists. Keep decisions concise.",
            str(uuid.uuid4()),
            extra_params=extra_params if native_search_enabled else None,
        )
        coordinator_agent.agent_name = "coordinator_agent"
        task_agent = _build_agent(
            provider,
            "You are a task planning agent that decomposes complex work into clear, self-contained tasks.",
            str(uuid.uuid4()),
            stream=True,
            extra_params=extra_params if native_search_enabled else None,
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
        if not search_enabled:
            for spec in agent_specs:
                spec.tools = _strip_search_tools(spec.tools, include_browser=True)
        elif native_search_enabled:
            for spec in agent_specs:
                spec.tools = _strip_search_tools(spec.tools, include_browser=False)
        if memory_search_enabled:
            _ensure_tool(agent_specs, "memory_search")
        if not skill_engine.is_shadow():
            apply_runtime_skills(agent_specs, active_skills)
        global_base_context = _build_global_base_context(str(workdir), action.project_id)
        skill_context = build_runtime_skill_context(active_skills)
        if skill_context:
            global_base_context = f"{global_base_context}{skill_context}"
        search_backend = "exa" if search_enabled and not native_search_enabled else None

        async def _approval_callback(**payload: Any) -> bool:
            return await _request_tool_permission(
                task_lock=task_lock,
                event_stream=event_stream,
                toolkit_name=str(payload.get("toolkit_name") or ""),
                method_name=str(payload.get("method_name") or ""),
                message=str(payload.get("message") or ""),
                agent_name=str(payload.get("agent_name") or ""),
                process_task_id=str(payload.get("process_task_id") or ""),
            )

        for spec in agent_specs:
            tools = build_agent_tools(
                spec.tools or [],
                event_stream,
                spec.name,
                str(workdir),
                mcp_tools=mcp_tools,
                search_backend=search_backend,
                approval_callback=_approval_callback,
            )
            full_system_prompt = global_base_context + spec.system_prompt
            agent = _build_agent(
                provider,
                full_system_prompt,
                spec.agent_id,
                tools=tools,
                extra_params=extra_params if native_search_enabled else None,
            )
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
            event_stream.emit(StepEvent.turn_cancelled, {"reason": "user_stop"})
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
        summary_result = ""
        summary_streamed = False
        if len(camel_subtasks) > 1:
            results_prompt = build_results_summary_prompt(action.question, task_nodes)
            results_usage: dict | None = None
            summary_parts: list[str] = []
            try:
                async for chunk, usage_update in stream_chat(
                    provider,
                    [
                        {"role": "system", "content": "You summarize results."},
                        {"role": "user", "content": results_prompt},
                    ],
                    temperature=0.2,
                    extra_params=extra_params,
                ):
                    if task_lock.stop_requested:
                        break
                    if chunk:
                        summary_streamed = True
                        summary_parts.append(chunk)
                        event_stream.emit(StepEvent.streaming, {"chunk": chunk})
                    if usage_update:
                        results_usage = usage_update
            except Exception as exc:
                event_stream.emit(StepEvent.error, {"error": str(exc)})
                event_stream.emit(
                    StepEvent.end,
                    {"result": "error", "reason": "Result summary failed"},
                )
                if history_id is not None:
                    await update_history(action.auth_token, history_id, {"status": 3})
                task_lock.status = TaskStatus.done
                return

            if task_lock.stop_requested:
                event_stream.emit(StepEvent.turn_cancelled, {"reason": "user_stop"})
                event_stream.emit(
                    StepEvent.end,
                    {"result": "stopped", "reason": "user_stop"},
                )
                if history_id is not None:
                    await update_history(action.auth_token, history_id, {"status": 3})
                task_lock.status = TaskStatus.stopped
                return

            token_tracker.add(results_usage)
            summary_result = "".join(summary_parts).strip()
            if summary_result:
                final_result = summary_result
        if not task_lock.last_task_summary and final_result:
            task_lock.last_task_summary = final_result
            await upsert_task_summary(
                action.auth_token,
                action.task_id,
                final_result,
                project_id=action.project_id,
            )

        if not final_result:
            final_result = "Task completed."

        if final_result and (not summary_streamed or not summary_result):
            event_stream.emit(StepEvent.streaming, {"chunk": final_result})

        if skill_run_state and skill_run_state.active_skills:
            validation = skill_engine.validate_outputs(
                run_state=skill_run_state,
                workdir=workdir,
                transcript=final_result,
            )
            primary_skill = skill_run_state.active_skills[0]
            event_stream.emit(
                StepEvent.notice,
                {
                    "message": "Validating runtime skill output contracts.",
                    "skill_id": primary_skill.id,
                    "skill_version": primary_skill.version,
                    "skill_stage": "validate_outputs",
                    "skill_score": validation.score,
                    "validation": {
                        "success": validation.success,
                        "issues": validation.issues,
                        "expected_contracts": validation.expected_contracts,
                    },
                },
            )
            _trace_log(
                "skill_validation",
                {
                    "task_id": action.task_id,
                    "success": validation.success,
                    "score": validation.score,
                    "issues": validation.issues,
                },
            )
            if not validation.success:
                event_stream.emit(
                    StepEvent.notice,
                    {
                        "message": "Attempting a repair pass for skill contracts.",
                        "skill_id": primary_skill.id,
                        "skill_version": primary_skill.version,
                        "skill_stage": "repair",
                        "skill_checkpoint": "repair_attempt",
                        "validation": {
                            "success": validation.success,
                            "issues": validation.issues,
                            "expected_contracts": validation.expected_contracts,
                        },
                    },
                )
                repair = skill_engine.repair_or_fail(
                    run_state=skill_run_state,
                    validation=validation,
                    workdir=workdir,
                )
                for artifact in repair.artifacts:
                    event_stream.emit(StepEvent.artifact, artifact)
                _trace_log(
                    "skill_repair_attempt",
                    {
                        "task_id": action.task_id,
                        "success": repair.success,
                        "notes": repair.notes,
                        "artifacts": repair.artifacts,
                    },
                )
                if not repair.success:
                    reason = "Skill output contract validation failed"
                    event_stream.emit(
                        StepEvent.error,
                        {
                            "error": reason,
                            "skill_id": primary_skill.id,
                            "skill_version": primary_skill.version,
                            "skill_stage": "validation_failed",
                            "validation": {
                                "success": validation.success,
                                "issues": validation.issues,
                                "expected_contracts": validation.expected_contracts,
                            },
                        },
                    )
                    event_stream.emit(
                        StepEvent.end,
                        {
                            "result": "error",
                            "reason": reason,
                            "skill_id": primary_skill.id,
                            "skill_version": primary_skill.version,
                            "skill_stage": "validation_failed",
                            "validation": {
                                "success": validation.success,
                                "issues": validation.issues,
                                "expected_contracts": validation.expected_contracts,
                            },
                        },
                    )
                    if history_id is not None:
                        await update_history(action.auth_token, history_id, {"status": 3})
                    task_lock.status = TaskStatus.done
                    return

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
        task_lock.add_conversation("assistant", final_result)
        await _persist_message(
            action.auth_token,
            action.project_id,
            action.task_id,
            "assistant",
            final_result,
            "task_result",
        )
        if memory_generate_enabled:
            task_lock.add_background_task(
                asyncio.create_task(
                    _generate_global_memory_notes(task_lock, provider, action.auth_token)
                )
            )
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
        if mcp_toolkit is not None:
            try:
                await mcp_toolkit.disconnect()
            except Exception:
                pass
        if env_snapshot is not None:
            _restore_env(env_snapshot)
        task_lock.workforce = None
        event_stream.close()
