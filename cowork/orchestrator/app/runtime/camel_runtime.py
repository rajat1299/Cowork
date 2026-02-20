from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from app.clients.core_api import (
    ProviderConfig,
    create_history,
    fetch_configs,
    fetch_mcp_users,
    fetch_provider,
    fetch_provider_features,
    fetch_skills,
    update_history,
    upsert_task_summary,
)
from app.runtime.actions import ActionType, TaskStatus
from app.runtime.agents import CoworkWorkforce, _build_agent
from app.runtime.artifacts import (
    _build_generated_file_url,
    _cleanup_artifact_cache,
    _collect_tool_artifacts,
    _extract_file_artifacts,
)
from app.runtime.config_helpers import (
    _config_flag,
    _is_permission_approved,
    _requires_tool_permission,
)
from app.runtime.context import _attachments_context, _normalize_attachments, _resolve_workdir
from app.runtime.events import StepEvent
from app.runtime.executor import _run_camel_complex
from app.runtime.llm_client import collect_chat_completion, stream_chat
from app.runtime.memory import (
    _build_context,
    _compact_context,
    _conversation_length,
    _generate_global_memory_notes,
    _hydrate_conversation_history,
    _hydrate_memory_notes,
    _hydrate_task_summary,
    _hydrate_thread_summary,
    _persist_message,
    _usage_total,
)
from app.runtime.mcp_config import _build_mcp_config, _load_mcp_tools
from app.runtime.skill_catalog_matching import (
    catalog_skill_matches_request,
    extensions_for_skill_detection,
    filter_enabled_runtime_skills,
)
from app.runtime.skill_engine import get_runtime_skill_engine
from app.runtime.skills import (
    RuntimeSkill,
    apply_runtime_skills,
    build_runtime_skill_context,
    detect_runtime_skills,
    requires_complex_execution,
    skill_ids,
    skill_names,
)
from app.runtime.streaming import EventStream, TokenTracker, _emit
from app.runtime.task_analysis import (
    _build_native_search_params,
    _detect_custom_runtime_skills,
    _detect_search_intent,
    _ensure_tool,
    _is_complex_task,
    _merge_agent_specs,
)
from app.runtime.task_lock import TaskLock
from app.runtime.tool_context import current_auth_token, current_project_id
from app.runtime.toolkits.camel_tools import build_agent_tools
from app.runtime.tracing import _trace_log
from app.runtime.workforce import build_default_agents, parse_subtasks
from app.runtime.sync import fire_and_forget, fire_and_forget_artifact
from shared.schemas import StepEvent as StepEventModel


logger = logging.getLogger(__name__)

_MAX_CONTEXT_LENGTH = 100000
_COMPACTION_TRIGGER = 80000

async def run_task_loop(task_lock: TaskLock) -> AsyncIterator[StepEventModel]:
    while True:
        try:
            action = await task_lock.get()
        except asyncio.CancelledError:
            break

        if action.type == ActionType.improve:
            current_auth_token.set(action.auth_token)
            current_project_id.set(action.project_id)
            _trace_log(
                "action_received",
                {
                    "task_id": action.task_id,
                    "project_id": action.project_id,
                    "question_preview": action.question[:200],
                    "search_enabled": action.search_enabled,
                    "provider_id": action.provider_id,
                    "model_provider": action.model_provider,
                    "model_type": action.model_type,
                },
            )
            task_lock.stop_requested = False
            task_lock.status = TaskStatus.processing
            task_lock.current_task_id = action.task_id
            _cleanup_artifact_cache(action.task_id)
            await _hydrate_conversation_history(task_lock, action.auth_token, action.project_id)
            await _hydrate_thread_summary(task_lock, action.auth_token, action.project_id)

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

            _trace_log(
                "provider_resolved",
                {
                    "task_id": action.task_id,
                    "provider_id": provider.id,
                    "provider_name": provider.provider_name,
                    "model_type": provider.model_type,
                    "endpoint_url": provider.endpoint_url,
                    "prefer": provider.prefer,
                },
            )

            feature_flags = None
            if provider.id:
                feature_flags = await fetch_provider_features(
                    action.auth_token,
                    provider.id,
                    provider.model_type,
                )
            if action.search_enabled is None:
                search_enabled = _detect_search_intent(action.question)
            else:
                search_enabled = bool(action.search_enabled)
            native_search_params = _build_native_search_params(provider)
            native_search_enabled = bool(
                search_enabled
                and feature_flags
                and feature_flags.native_web_search_enabled
                and provider.api_key
                and native_search_params
            )
            _trace_log(
                "search_routing",
                {
                    "task_id": action.task_id,
                    "search_enabled": search_enabled,
                    "native_search_enabled": native_search_enabled,
                    "feature_flags": bool(feature_flags),
                    "native_params": bool(native_search_params),
                },
            )
            extra_params = None
            if native_search_enabled:
                extra_params = feature_flags.extra_params_json or native_search_params
            if (
                search_enabled
                and not native_search_enabled
                and provider.id == 0
                and native_search_params
            ):
                native_search_enabled = True
                extra_params = native_search_params
            exa_fallback_enabled = search_enabled and not native_search_enabled
            memory_configs = await fetch_configs(action.auth_token, group="memory")
            memory_generate_enabled = _config_flag(
                memory_configs,
                "MEMORY_GENERATE_FROM_CHATS",
                default=True,
            )

            context_length = _conversation_length(task_lock)
            if context_length > _COMPACTION_TRIGGER:
                yield _emit(
                    action.task_id,
                    StepEvent.notice,
                    {"message": "Compacting conversation so we can keep chatting..."},
                )
                try:
                    await _compact_context(task_lock, provider, action.auth_token, action.project_id)
                except Exception as exc:
                    logger.warning("Context compaction failed: %s", exc)

            await _hydrate_task_summary(task_lock, action.auth_token, action.task_id)
            await _hydrate_memory_notes(
                task_lock,
                action.auth_token,
                action.project_id,
                include_global=memory_generate_enabled,
            )

            context_length = _conversation_length(task_lock)
            if context_length > _MAX_CONTEXT_LENGTH:
                yield _emit(
                    action.task_id,
                    StepEvent.context_too_long,
                    {
                        "message": "The conversation history is too long. Please create a new project to continue.",
                        "current_length": context_length,
                        "max_length": _MAX_CONTEXT_LENGTH,
                    },
                )
                continue

            yield _emit(action.task_id, StepEvent.confirmed, {"question": action.question})
            yield _emit(action.task_id, StepEvent.task_state, {"state": "processing"})

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
            workdir = _resolve_workdir(action.project_id)
            attachments = _normalize_attachments(action.attachments, workdir)
            attachments_text = _attachments_context(attachments)
            context = _build_context(task_lock)
            context_with_attachments = f"{context}{attachments_text}" if attachments_text else context
            skill_engine = get_runtime_skill_engine()
            skill_catalog = await fetch_skills(action.auth_token)
            enabled_catalog_skills = [entry for entry in (skill_catalog or []) if entry.enabled]
            detection_extensions = extensions_for_skill_detection(action.question, attachments)
            detected_skills = detect_runtime_skills(action.question, attachments)
            custom_skill_candidates = [
                entry
                for entry in enabled_catalog_skills
                if entry.source == "custom"
                and catalog_skill_matches_request(entry, action.question, detection_extensions)
            ]
            custom_detected_skills = _detect_custom_runtime_skills(
                action.question,
                detection_extensions,
                custom_skill_candidates,
            )
            if custom_detected_skills:
                combined: list[RuntimeSkill] = []
                seen_ids: set[str] = set()
                for skill in [*detected_skills, *custom_detected_skills]:
                    if skill.id in seen_ids:
                        continue
                    seen_ids.add(skill.id)
                    combined.append(skill)
                detected_skills = combined
            active_skills = filter_enabled_runtime_skills(
                detected_skills,
                skill_catalog,
            )
            skill_run_state = skill_engine.prepare_plan(
                task_id=action.task_id,
                project_id=action.project_id,
                question=action.question,
                context=context_with_attachments,
                active_skills=active_skills,
            )
            skills_context = build_runtime_skill_context(active_skills)
            context_with_skills = (
                f"{context_with_attachments}{skills_context}" if skills_context else context_with_attachments
            )
            if active_skills:
                _trace_log(
                    "skill_detected",
                    {
                        "task_id": action.task_id,
                        "skill_ids": skill_ids(active_skills),
                        "skills": skill_names(active_skills),
                        "query_plan": skill_run_state.query_plan,
                    },
                )
                yield _emit(
                    action.task_id,
                    StepEvent.notice,
                    {
                        "message": f"Activated skills: {', '.join(skill_names(active_skills))}",
                        "skill_id": active_skills[0].id,
                        "skill_version": active_skills[0].version,
                        "skill_stage": "detect",
                        "skill_checkpoint": "skills_activated",
                        "skill_score": skill_engine.score_parity_profile().get("weighted_score"),
                        "validation": {
                            "skill_ids": skill_ids(active_skills),
                            "query_plan": skill_run_state.query_plan,
                        },
                    },
                )
            elif detected_skills:
                yield _emit(
                    action.task_id,
                    StepEvent.notice,
                    {
                        "message": "Detected skills are disabled in your Capabilities settings.",
                        "skill_stage": "detect",
                        "validation": {
                            "detected_skill_ids": skill_ids(detected_skills),
                        },
                    },
                )
            await _persist_message(
                action.auth_token,
                action.project_id,
                action.task_id,
                "user",
                action.question,
                "user",
                metadata={"attachments": attachments} if attachments else None,
            )
            conversation_text = action.question
            if attachments_text:
                conversation_text = f"{conversation_text}\n{attachments_text.strip()}"
            task_lock.add_conversation("user", conversation_text)
            is_complex, complexity_tokens = await _is_complex_task(
                provider,
                action.question,
                context_with_skills,
            )
            total_tokens += complexity_tokens
            if exa_fallback_enabled:
                is_complex = True
            skill_forces_complex = requires_complex_execution(action.question, active_skills)
            if skill_forces_complex and skill_engine.is_shadow():
                _trace_log(
                    "skill_stage",
                    {
                        "task_id": action.task_id,
                        "stage": "force_complex_shadow_only",
                        "skill_ids": skill_ids(active_skills),
                    },
                )
            elif skill_forces_complex:
                is_complex = True

            if not is_complex:
                content_parts: list[str] = []
                usage: dict | None = None
                try:
                    if native_search_enabled:
                        prompt = (
                            f"{context_with_skills}User Query: {action.question}\n\n"
                            "Provide a direct, helpful answer. Use web search if it helps."
                        )
                    else:
                        prompt = (
                            f"{context_with_skills}User Query: {action.question}\n\n"
                            "Provide a direct, helpful answer to this simple question."
                        )
                    messages = [{"role": "user", "content": prompt}]
                    async for chunk, usage_update in stream_chat(
                        provider,
                        messages,
                        extra_params=extra_params,
                    ):
                        if task_lock.stop_requested:
                            break
                        if chunk:
                            content_parts.append(chunk)
                            yield _emit(action.task_id, StepEvent.streaming, {"chunk": chunk})
                            if skill_run_state and skill_run_state.active_skills:
                                skill_engine.on_step_event(skill_run_state, StepEvent.streaming.value, {"chunk": chunk})
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
                        StepEvent.turn_cancelled,
                        {"reason": "user_stop"},
                    )
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

                if result_text:
                    task_lock.last_task_summary = result_text
                    await upsert_task_summary(
                        action.auth_token,
                        action.task_id,
                        result_text,
                        project_id=action.project_id,
                    )

                if skill_run_state and skill_run_state.active_skills:
                    skill_engine.on_step_event(skill_run_state, StepEvent.end.value, {"result": result_text})
                    validation = skill_engine.validate_outputs(
                        run_state=skill_run_state,
                        workdir=workdir,
                        transcript=result_text,
                    )
                    if not validation.success:
                        repair = skill_engine.repair_or_fail(
                            run_state=skill_run_state,
                            validation=validation,
                            workdir=workdir,
                        )
                        for artifact in repair.artifacts:
                            yield _emit(action.task_id, StepEvent.artifact, artifact)
                            skill_engine.on_step_event(skill_run_state, StepEvent.artifact.value, artifact)
                        if not repair.success:
                            reason = "Skill output contract validation failed"
                            yield _emit(
                                action.task_id,
                                StepEvent.error,
                                {
                                    "error": reason,
                                    "skill_id": skill_run_state.active_skills[0].id,
                                    "skill_version": skill_run_state.active_skills[0].version,
                                    "skill_stage": "validation_failed",
                                    "validation": {
                                        "success": validation.success,
                                        "issues": validation.issues,
                                        "expected_contracts": validation.expected_contracts,
                                    },
                                },
                            )
                            yield _emit(
                                action.task_id,
                                StepEvent.end,
                                {
                                    "result": "error",
                                    "reason": reason,
                                    "skill_id": skill_run_state.active_skills[0].id,
                                    "skill_version": skill_run_state.active_skills[0].version,
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
                            continue

                yield _emit(action.task_id, StepEvent.end, {"result": result_text, "usage": usage or {}})
                task_lock.add_conversation("assistant", result_text)
                await _persist_message(
                    action.auth_token,
                    action.project_id,
                    action.task_id,
                    "assistant",
                    result_text,
                    "assistant",
                )
                if memory_generate_enabled:
                    task_lock.add_background_task(
                        asyncio.create_task(
                            _generate_global_memory_notes(task_lock, provider, action.auth_token)
                        )
                    )
                task_lock.status = TaskStatus.done
                continue

            loop = asyncio.get_running_loop()
            event_stream = EventStream(
                action.task_id,
                loop,
                step_listener=(
                    (lambda step, data: skill_engine.on_step_event(skill_run_state, step.value, data))
                    if skill_run_state and skill_run_state.active_skills
                    else None
                ),
            )
            token_tracker = TokenTracker(total_tokens)
            run_task = asyncio.create_task(
                _run_camel_complex(
                    task_lock,
                    action,
                    provider,
                    extra_params,
                    search_enabled,
                    native_search_enabled,
                    history_id,
                    token_tracker,
                    event_stream,
                    context_with_skills,
                    memory_generate_enabled,
                    active_skills,
                    skill_run_state,
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
                StepEvent.turn_cancelled,
                {"reason": action.reason},
            )
            yield _emit(
                task_lock.current_task_id or "unknown",
                StepEvent.end,
                {"result": "stopped", "reason": action.reason},
            )
            break
