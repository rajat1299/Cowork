from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterable
from urllib.parse import quote

from camel.agents import ChatAgent
from camel.agents.chat_agent import AsyncStreamingChatAgentResponse
from camel.models import ModelFactory
from camel.toolkits.mcp_toolkit import MCPToolkit
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

from app.clients.core_api import (
    ProviderConfig,
    SkillEntry,
    create_history,
    create_message,
    create_memory_note,
    fetch_configs,
    fetch_messages,
    fetch_memory_notes,
    fetch_mcp_users,
    fetch_provider,
    fetch_provider_features,
    fetch_skills,
    fetch_task_summary,
    fetch_thread_summary,
    upsert_task_summary,
    upsert_thread_summary,
    update_history,
)
from app.runtime.actions import ActionType, AgentSpec, TaskStatus
from app.runtime.events import StepEvent
from app.runtime.llm_client import (
    _ANTHROPIC_NAMES,
    _OPENAI_COMPAT_DEFAULTS,
    _OPENAI_COMPAT_REQUIRES_ENDPOINT,
    _normalize_provider_name,
    collect_chat_completion,
    stream_chat,
)
from app.runtime.skill_engine import SkillRunState, get_runtime_skill_engine
from app.runtime.skills import (
    RuntimeSkill,
    apply_runtime_skills,
    build_runtime_skill_context,
    detect_runtime_skills,
    requires_complex_execution,
    skill_ids,
    skill_names,
)
from app.runtime.skills_schema import load_skill_packs
from app.runtime.sync import fire_and_forget, fire_and_forget_artifact
from app.runtime.task_lock import TaskLock
from app.runtime.tool_context import (
    current_agent_name,
    current_auth_token,
    current_process_task_id,
    current_project_id,
)
from app.runtime.toolkits.camel_tools import build_agent_tools
from app.runtime.camel_agent import CoworkChatAgent
from app.runtime.workforce import (
    AgentProfile,
    build_complexity_prompt,
    build_decomposition_prompt,
    build_default_agents,
    build_results_summary_prompt,
    build_summary_prompt,
    parse_subtasks,
)
from shared.schemas import AgentEvent, ArtifactEvent, StepEvent as StepEventModel


logger = logging.getLogger(__name__)
_TRACE_LOGGER: logging.Logger | None = None

_MAX_CONTEXT_LENGTH = 100000
_COMPACTION_TRIGGER = 80000
_COMPACTION_KEEP_LAST = 12
_FILE_ARTIFACT_PATTERNS = (
    re.compile(
        r"(?:content\s+successfully\s+)?(?:written|saved|created)\s+to\s+file\s*:\s*(?P<path>[^\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:output|artifact|file)\s*:\s*(?P<path>[^\n]+?\.[a-z0-9]{1,8})",
        re.IGNORECASE,
    ),
)
_ABSOLUTE_FILE_PATTERN = re.compile(r"(/[^\s'\"`]+\.[a-z0-9]{1,8})", re.IGNORECASE)
_ARTIFACT_TYPE_BY_EXTENSION = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
}
_ARTIFACT_DEDUPE: dict[str, set[str]] = {}
_ARTIFACT_DEDUPE_LOCK = threading.Lock()
GLOBAL_USER_CONTEXT = "GLOBAL_USER_CONTEXT"
GLOBAL_MEMORY_CATEGORIES = {
    "work_context",
    "personal_context",
    "tech_stack",
    "preferences",
}


def _get_trace_logger() -> logging.Logger:
    global _TRACE_LOGGER
    if _TRACE_LOGGER is not None:
        return _TRACE_LOGGER

    log_path = os.environ.get("COWORK_RUNTIME_LOG_PATH")
    if not log_path:
        log_path = os.path.expanduser("~/.cowork/logs/runtime.log")

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    trace_logger = logging.getLogger("cowork.runtime.trace")
    trace_logger.setLevel(logging.INFO)
    trace_logger.propagate = False
    if not trace_logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        trace_logger.addHandler(handler)
    _TRACE_LOGGER = trace_logger
    return trace_logger


def _trace_log(event: str, payload: dict[str, Any]) -> None:
    logger = _get_trace_logger()
    payload = {**payload, "event": event, "ts": datetime.utcnow().isoformat() + "Z"}
    logger.info(json.dumps(payload))


def _trace_step(task_id: str, step: StepEvent, data: dict) -> None:
    if step in {StepEvent.streaming, StepEvent.decompose_text}:
        chunk = data.get("chunk") if step == StepEvent.streaming else data.get("content")
        if isinstance(chunk, str):
            preview = chunk[:200]
            _trace_log(
                "step",
                {
                    "task_id": task_id,
                    "step": step.value,
                    "chunk_len": len(chunk),
                    "chunk_preview": preview,
                },
            )
            return
    data_preview = repr(data)
    if len(data_preview) > 2000:
        data_preview = data_preview[:2000] + "...(truncated)"
    _trace_log(
        "step",
        {
            "task_id": task_id,
            "step": step.value,
            "data": data_preview,
        },
    )


def _emit(task_id: str, step: StepEvent, data: dict) -> StepEventModel:
    artifact_payloads: list[dict[str, Any]] = []
    if step == StepEvent.deactivate_toolkit:
        artifact_payloads = _collect_tool_artifacts(task_id, data)
    _trace_step(task_id, step, data)
    payload = _attach_agent_event(task_id, step, data)
    event = StepEventModel(
        task_id=task_id,
        step=step,
        data=payload,
        timestamp=time.time(),
    )
    fire_and_forget(event)
    for artifact_payload in artifact_payloads:
        _emit(task_id, StepEvent.artifact, artifact_payload)
    return event


def _attach_agent_event(task_id: str, step: StepEvent, data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    if "agent_event" in data:
        return data
    agent_event = _build_agent_event(task_id, step, data)
    if agent_event is None:
        return data
    return {**data, "agent_event": agent_event}


def _build_agent_event(task_id: str, step: StepEvent, data: dict) -> dict | None:
    event_type = _map_step_to_agent_event(step)
    if event_type is None:
        return None
    payload = _agent_event_payload(step, data)
    timestamp_ms = int(time.time() * 1000)
    session_id = data.get("project_id") or current_project_id.get(None)
    event = AgentEvent(
        type=event_type,
        payload=payload,
        timestamp_ms=timestamp_ms,
        turn_id=task_id,
        session_id=session_id,
    )
    return event.model_dump(exclude_none=True)


def _map_step_to_agent_event(step: StepEvent) -> str | None:
    if step == StepEvent.confirmed:
        return "message_start"
    if step == StepEvent.streaming:
        return "text_delta"
    if step == StepEvent.decompose_text:
        return "text_delta"
    if step == StepEvent.end:
        return "message_end"
    if step == StepEvent.activate_toolkit:
        return "tool_exec_start"
    if step == StepEvent.deactivate_toolkit:
        return "tool_exec_end"
    if step == StepEvent.error:
        return "error"
    if step == StepEvent.notice:
        return "notice"
    if step == StepEvent.ask_user:
        return "ask_user"
    if step == StepEvent.turn_cancelled:
        return "turn_cancelled"
    if step in {
        StepEvent.context_too_long,
        StepEvent.to_sub_tasks,
        StepEvent.assign_task,
        StepEvent.task_state,
        StepEvent.create_agent,
        StepEvent.activate_agent,
        StepEvent.deactivate_agent,
    }:
        return "state_boundary"
    return None


def _agent_event_payload(step: StepEvent, data: dict) -> dict:
    if step == StepEvent.streaming:
        return {"text": data.get("chunk", "")}
    if step == StepEvent.decompose_text:
        return {"text": data.get("content", ""), "channel": "decompose"}
    if step == StepEvent.confirmed:
        return {"question": data.get("question")}
    if step == StepEvent.activate_toolkit:
        return {
            "toolkit": data.get("toolkit_name"),
            "method": data.get("method_name"),
            "agent_name": data.get("agent_name"),
            "process_task_id": data.get("process_task_id"),
            "args": data.get("message"),
        }
    if step == StepEvent.deactivate_toolkit:
        return {
            "toolkit": data.get("toolkit_name"),
            "method": data.get("method_name"),
            "agent_name": data.get("agent_name"),
            "process_task_id": data.get("process_task_id"),
            "result": data.get("message"),
        }
    if step == StepEvent.error:
        return {"message": data.get("error") or data.get("message")}
    if step == StepEvent.ask_user:
        return data
    if step == StepEvent.turn_cancelled:
        return {"reason": data.get("reason")}
    if step == StepEvent.end:
        return data
    return {"kind": step.value, "data": data}


def _collect_tool_artifacts(task_id: str, data: dict) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    payloads.extend(_extract_file_artifacts(task_id, data))
    return payloads


def _artifact_type_from_suffix(path: Path) -> str:
    return _ARTIFACT_TYPE_BY_EXTENSION.get(path.suffix.lower(), "file")


def _resolve_runtime_base_path(task_id: str) -> Path:
    workdir = os.environ.get("CAMEL_WORKDIR")
    if workdir:
        return Path(workdir)
    project_id = current_project_id.get(None) or task_id
    return _resolve_workdir(project_id)


def _build_generated_file_url(base_path: Path, file_path: Path) -> str | None:
    project_id = (
        current_project_id.get(None)
        or _infer_project_id_from_workdir(base_path)
        or _infer_project_id_from_workdir(file_path)
    )
    if not project_id:
        return None
    try:
        relative_path = file_path.relative_to(base_path)
    except ValueError:
        return None
    return f"/files/generated/{project_id}/download?path={quote(str(relative_path))}"


def _infer_project_id_from_workdir(path: Path) -> str | None:
    try:
        resolved = path.resolve()
    except Exception:
        return None
    parts = resolved.parts
    for index, value in enumerate(parts[:-1]):
        if value == "workdir" and index + 1 < len(parts):
            candidate = parts[index + 1]
            if candidate:
                return candidate
    return None


def _mark_artifact_emitted(task_id: str, key: str) -> bool:
    with _ARTIFACT_DEDUPE_LOCK:
        emitted = _ARTIFACT_DEDUPE.setdefault(task_id, set())
        if key in emitted:
            return False
        emitted.add(key)
        return True


def _cleanup_artifact_cache(task_id: str) -> None:
    with _ARTIFACT_DEDUPE_LOCK:
        _ARTIFACT_DEDUPE.pop(task_id, None)


def _normalize_result_path(raw_path: str, base_path: Path) -> Path | None:
    value = raw_path.strip().strip("`'\"")
    value = value.rstrip(".,;")
    if not value:
        return None
    try:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = (base_path / candidate).resolve()
        else:
            candidate = candidate.resolve()
    except Exception:
        return None
    return candidate


def _candidate_paths_from_message(message: str) -> list[str]:
    candidates: list[str] = []
    for pattern in _FILE_ARTIFACT_PATTERNS:
        for match in pattern.finditer(message):
            path_value = match.groupdict().get("path")
            if path_value:
                candidates.append(path_value.strip())
    if not candidates:
        for match in _ABSOLUTE_FILE_PATTERN.finditer(message):
            candidates.append(match.group(1))
    return candidates


def _extract_file_artifacts(task_id: str, data: dict) -> list[dict[str, Any]]:
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return []

    base_path = _resolve_runtime_base_path(task_id)
    now = time.time()
    artifact_payloads: list[dict[str, Any]] = []

    for raw_path in _candidate_paths_from_message(message):
        resolved = _normalize_result_path(raw_path, base_path)
        if resolved is None or not resolved.exists() or not resolved.is_file():
            continue

        path_key = str(resolved)
        if not _mark_artifact_emitted(task_id, path_key):
            continue

        content_url = _build_generated_file_url(base_path, resolved)
        artifact_type = _artifact_type_from_suffix(resolved)
        fire_and_forget_artifact(
            ArtifactEvent(
                task_id=task_id,
                artifact_type=artifact_type,
                name=resolved.name,
                content_url=content_url or str(resolved),
                created_at=now,
            )
        )
        artifact_payloads.append(
            {
                "id": f"artifact-file-{abs(hash((task_id, path_key, int(now * 1000))))}",
                "type": artifact_type,
                "name": resolved.name,
                "content_url": content_url or str(resolved),
                "path": str(resolved),
            }
        )

    return artifact_payloads


def _usage_total(usage: dict | None) -> int:
    if not usage:
        return 0
    return int(usage.get("total_tokens") or 0)

def _append_memory_notes(lines: list[str], title: str, notes: list[dict[str, object]]) -> None:
    if not notes:
        return
    lines.append(title)
    pinned = [note for note in notes if note.get("pinned")]
    other = [note for note in notes if not note.get("pinned")]
    for note in pinned + other:
        content = note.get("content", "")
        category = note.get("category", "note")
        label = "pinned" if note.get("pinned") else category
        lines.append(f"- ({label}) {content}")
    lines.append("")


def _build_context(task_lock: TaskLock) -> str:
    if (
        not task_lock.conversation_history
        and not task_lock.thread_summary
        and not task_lock.last_task_summary
        and not task_lock.memory_notes
        and not task_lock.global_memory_notes
    ):
        return ""
    lines: list[str] = []
    if task_lock.thread_summary:
        lines.extend(
            [
                "=== Thread Summary ===",
                task_lock.thread_summary,
                "",
            ]
        )
    if task_lock.last_task_summary:
        lines.extend(
            [
                "=== Task Summary ===",
                task_lock.last_task_summary,
                "",
            ]
        )
    _append_memory_notes(lines, "=== User Preferences ===", task_lock.global_memory_notes)
    _append_memory_notes(lines, "=== Project Context ===", task_lock.memory_notes)
    if not task_lock.conversation_history:
        return "\n".join(lines).strip() + "\n"
    lines.append("=== Previous Conversation ===")
    for entry in task_lock.conversation_history:
        role = entry.get("role") or "assistant"
        content = entry.get("content") or ""
        if role == "assistant":
            lines.append(f"Assistant: {content}")
        else:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) + "\n"


def _conversation_length(task_lock: TaskLock) -> int:
    total_length = 0
    if task_lock.thread_summary:
        total_length += len(task_lock.thread_summary)
    if task_lock.last_task_summary:
        total_length += len(task_lock.last_task_summary)
    for note in task_lock.memory_notes:
        content = note.get("content", "")
        total_length += len(content) if isinstance(content, str) else len(str(content))
    for note in task_lock.global_memory_notes:
        content = note.get("content", "")
        total_length += len(content) if isinstance(content, str) else len(str(content))
    for entry in task_lock.conversation_history:
        content = entry.get("content", "")
        total_length += len(content) if isinstance(content, str) else len(str(content))
    return total_length


async def _hydrate_conversation_history(
    task_lock: TaskLock,
    auth_token: str | None,
    project_id: str,
) -> None:
    if task_lock.conversation_history:
        return
    messages = await fetch_messages(auth_token, project_id=project_id)
    if not messages:
        return
    task_lock.conversation_history = [
        {
            "role": message.role,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
        }
        for message in messages
    ]
    for message in reversed(messages):
        if message.role == "assistant":
            task_lock.last_task_result = message.content
            break


async def _hydrate_thread_summary(
    task_lock: TaskLock,
    auth_token: str | None,
    project_id: str,
) -> None:
    if task_lock.thread_summary:
        return
    summary = await fetch_thread_summary(auth_token, project_id)
    if summary and summary.summary:
        task_lock.thread_summary = summary.summary


async def _hydrate_task_summary(
    task_lock: TaskLock,
    auth_token: str | None,
    task_id: str,
) -> None:
    summary = await fetch_task_summary(auth_token, task_id)
    if summary and summary.summary:
        task_lock.last_task_summary = summary.summary


async def _hydrate_memory_notes(
    task_lock: TaskLock,
    auth_token: str | None,
    project_id: str,
    include_global: bool = True,
) -> None:
    notes = await fetch_memory_notes(auth_token, project_id)
    task_lock.memory_notes = [note.model_dump() for note in notes]
    if include_global:
        global_notes = await fetch_memory_notes(auth_token, GLOBAL_USER_CONTEXT)
        task_lock.global_memory_notes = [note.model_dump() for note in global_notes]
    else:
        task_lock.global_memory_notes = []


async def _compact_context(
    task_lock: TaskLock,
    provider: ProviderConfig,
    auth_token: str | None,
    project_id: str,
) -> bool:
    if not task_lock.conversation_history:
        return False
    history_lines = []
    for entry in task_lock.conversation_history:
        role = entry.get("role") or "assistant"
        content = entry.get("content") or ""
        history_lines.append(f"{role}: {content}")
    history_text = "\n".join(history_lines)
    prompt = f"""Summarize the conversation for long-term memory.

Existing summary (if any):
{task_lock.thread_summary or "None"}

Conversation:
{history_text}

Return a concise summary with sections:
- Goal
- Decisions
- Outputs
- Open Questions
- Next Steps
"""
    summary_text, _ = await collect_chat_completion(
        provider,
        [{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    summary_text = summary_text.strip()
    if not summary_text:
        return False
    task_lock.thread_summary = summary_text
    await upsert_thread_summary(auth_token, project_id, summary_text)
    task_lock.conversation_history = task_lock.conversation_history[-_COMPACTION_KEEP_LAST:]
    return True


async def _generate_global_memory_notes(
    task_lock: TaskLock,
    provider: ProviderConfig,
    auth_token: str | None,
) -> None:
    if not auth_token or not task_lock.conversation_history:
        return
    existing_notes = await fetch_memory_notes(auth_token, GLOBAL_USER_CONTEXT)
    existing_dump = [note.model_dump() for note in existing_notes]
    existing_contents = {
        str(note.get("content", "")).strip().lower()
        for note in existing_dump
        if note.get("content")
    }
    existing_text = "\n".join(
        f"- ({note.get('category', 'note')}) {note.get('content', '')}"
        for note in existing_dump
        if note.get("content")
    ) or "None"
    history_lines = []
    for entry in task_lock.conversation_history:
        role = entry.get("role") or "assistant"
        content = entry.get("content") or ""
        history_lines.append(f"{role}: {content}")
    history_text = "\n".join(history_lines)
    prompt = f"""You are the Memory Manager. Your goal is to update the `GLOBAL_USER_CONTEXT` based on the conversation that just finished.

<existing_memory>
{existing_text}
</existing_memory>

<conversation_log>
{history_text}
</conversation_log>

<instructions>
1. **Filter**: Look ONLY for stable user preferences, facts, or technical constraints.
   - Examples: "User prefers TypeScript", "User works in CST timezone", "User hates unit tests".
2. **Ignore**: Transient task details ("Fix bug in line 50"), pleasantries, or one-off searches.
3. **Deduplicate**: If a fact already exists in `<existing_memory>`, DO NOT output it.
4. **Format**: Return a JSON array of objects: `[{{"category": "work_context", "content": "..."}}]`.
   - Categories: `work_context`, `personal_context`, `tech_stack`, `preferences`.
5. If no NEW long-term facts are found, return an empty array `[]`.
</instructions>
"""
    response_text, _ = await collect_chat_completion(
        provider,
        [{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    response_text = response_text.strip()
    if not response_text:
        return
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return
    if not isinstance(payload, list):
        return
    seen = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        category = str(item.get("category") or "").strip()
        if not content or category not in GLOBAL_MEMORY_CATEGORIES:
            continue
        norm = content.lower()
        if norm in existing_contents or norm in seen:
            continue
        seen.add(norm)
        await create_memory_note(
            auth_token,
            {
                "project_id": GLOBAL_USER_CONTEXT,
                "category": category,
                "content": content,
                "pinned": False,
            },
        )


async def _persist_message(
    auth_token: str | None,
    project_id: str,
    task_id: str,
    role: str,
    content: str,
    message_type: str,
    metadata: dict | None = None,
) -> None:
    payload = {
        "project_id": project_id,
        "task_id": task_id,
        "role": role,
        "content": content,
        "message_type": message_type,
        "metadata": metadata,
    }
    await create_message(auth_token, payload)


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


def _normalize_attachments(
    attachments: list[object] | None,
    workdir: Path,
) -> list[dict[str, object]]:
    if not attachments:
        return []
    safe: list[dict[str, object]] = []
    for attachment in attachments:
        payload: dict[str, object] | None = None
        if isinstance(attachment, dict):
            payload = attachment
        elif hasattr(attachment, "model_dump"):
            payload = attachment.model_dump()  # type: ignore[attr-defined]
        elif hasattr(attachment, "dict"):
            payload = attachment.dict()  # type: ignore[attr-defined]
        if not payload:
            continue
        raw_path = payload.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        try:
            resolved = Path(raw_path).expanduser().resolve()
        except Exception:
            continue
        if workdir not in resolved.parents and resolved != workdir:
            continue
        normalized = dict(payload)
        normalized["path"] = str(resolved)
        safe.append(normalized)
    return safe


def _attachments_context(attachments: list[dict[str, object]]) -> str:
    if not attachments:
        return ""
    lines = ["", "User attached files:"]
    for attachment in attachments:
        name = attachment.get("name") or "attachment"
        path = attachment.get("path") or ""
        content_type = attachment.get("content_type")
        size = attachment.get("size")
        meta_parts = []
        if isinstance(content_type, str) and content_type:
            meta_parts.append(content_type)
        if isinstance(size, int) and size > 0:
            meta_parts.append(f"{size} bytes")
        meta = f" ({', '.join(meta_parts)})" if meta_parts else ""
        lines.append(f"- {name}{meta}: {path}")
    return "\n".join(lines) + "\n"


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


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _config_flag(configs: list[dict[str, Any]], name: str, default: bool = False) -> bool:
    for item in configs:
        key = item.get("key") or item.get("name")
        if key != name:
            continue
        value = item.get("value")
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return default


def _agent_profile_from_spec(spec: AgentSpec) -> AgentProfile:
    name = (spec.name or "").strip()
    description = (spec.description or "").strip()
    system_prompt = (spec.system_prompt or "").strip()
    if not system_prompt:
        if description:
            system_prompt = f"You are {description}."
        else:
            system_prompt = f"You are {name}."
        system_prompt = f"{system_prompt} Use tools when needed. Be concise and actionable."
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


def _ensure_tool(agent_specs: list[AgentProfile], tool_name: str) -> None:
    for spec in agent_specs:
        if tool_name not in spec.tools:
            spec.tools.append(tool_name)


def _normalize_mcp_args(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return None


def _build_mcp_config(mcp_users: list[dict[str, object]]) -> dict[str, dict]:
    servers: dict[str, dict] = {}
    for item in mcp_users:
        status = item.get("status")
        if status and str(status).lower() != "enable":
            continue
        name = item.get("mcp_key") or item.get("mcp_name") or ""
        name = _sanitize_identifier(str(name), "mcp_server")
        mcp_type = str(item.get("mcp_type") or "local").lower()
        env = item.get("env") if isinstance(item.get("env"), dict) else {}
        if "MCP_REMOTE_CONFIG_DIR" not in env:
            env["MCP_REMOTE_CONFIG_DIR"] = str(Path.home() / ".cowork" / "mcp-auth")

        if mcp_type == "remote":
            server_url = item.get("server_url")
            if not server_url:
                continue
            servers[name] = {"url": server_url, "env": env}
            continue

        command = item.get("command")
        if not command:
            continue
        config: dict[str, object] = {"command": command}
        args = _normalize_mcp_args(item.get("args"))
        if args:
            config["args"] = args
        if env:
            config["env"] = env
        servers[name] = config

    return {"mcpServers": servers}


async def _load_mcp_tools(
    auth_token: str | None,
) -> tuple[MCPToolkit | None, list]:
    mcp_users = await fetch_mcp_users(auth_token)
    config = _build_mcp_config(mcp_users)
    if not config.get("mcpServers"):
        return None, []
    try:
        toolkit = MCPToolkit(config_dict=config, timeout=180)
        await toolkit.connect()
        return toolkit, toolkit.get_tools()
    except Exception as exc:
        logger.warning("MCP toolkit unavailable: %s", exc)
        return None, []


def _resolve_model_url(provider: ProviderConfig) -> str | None:
    if provider.endpoint_url:
        return provider.endpoint_url
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _OPENAI_COMPAT_DEFAULTS:
        return _OPENAI_COMPAT_DEFAULTS[normalized]
    if normalized in _OPENAI_COMPAT_REQUIRES_ENDPOINT:
        raise ValueError("Endpoint URL required for OpenAI-compatible provider")
    return None


def _build_native_search_params(provider: ProviderConfig) -> dict[str, Any] | None:
    normalized = _normalize_provider_name(provider.provider_name)
    if normalized in _ANTHROPIC_NAMES:
        return {
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }
            ]
        }
    if normalized == "openrouter":
        if not _openrouter_supports_native_web(provider.model_type):
            return None
        return {
            "plugins": [
                {
                    "id": "web",
                    "engine": "native",
                    "max_results": 3,
                }
            ]
        }
    if normalized in {"gemini", "google"}:
        return {"tools": [{"google_search": {}}]}
    if normalized == "openai":
        return {"tools": [{"type": "web_search"}], "tool_choice": "auto"}
    return None


def _openrouter_supports_native_web(model_type: str | None) -> bool:
    if not model_type:
        return False
    base = model_type.strip().lower().split(":", 1)[0]
    return base.startswith(
        (
            "openai/",
            "anthropic/",
            "perplexity/",
            "x-ai/",
            "xai/",
        )
    )


async def _is_complex_task(provider: ProviderConfig, question: str, context: str) -> tuple[bool, int]:
    prompt = build_complexity_prompt(question, context)
    messages = [
        {"role": "system", "content": "You are a classifier. Reply only \"yes\" or \"no\"."},
        {"role": "user", "content": prompt},
    ]
    text, usage = await collect_chat_completion(provider, messages, temperature=0.0)
    normalized = "".join(ch for ch in text.strip().lower() if ch.isalpha())
    if normalized.startswith("no"):
        return False, _usage_total(usage)
    if normalized.startswith("yes"):
        return True, _usage_total(usage)
    return True, _usage_total(usage)


def _strip_search_tools(tools: list[str], include_browser: bool) -> list[str]:
    blocked = {
        "search",
        "search_toolkit",
    }
    if include_browser:
        blocked.update(
            {
                "browser",
                "browser_toolkit",
                "hybrid_browser",
                "hybrid_browser_toolkit",
                "hybrid_browser_toolkit_py",
                "async_browser_toolkit",
            }
        )
    return [tool for tool in tools if tool not in blocked]


_SEARCH_INTENT_PATTERN = re.compile(
    r"\b(web\s+search|search the web|search online|search for|look up|lookup|google|bing|browse the web|find sources|latest news|recent news)\b",
    re.IGNORECASE,
)
_QUESTION_EXTENSION_PATTERN = re.compile(r"\.[a-zA-Z0-9]{1,8}\b")


def _detect_search_intent(question: str) -> bool:
    if not question:
        return False
    return bool(_SEARCH_INTENT_PATTERN.search(question))


def _extensions_for_skill_detection(question: str, attachments: list[object] | None) -> set[str]:
    question_extensions = {ext.lower() for ext in _QUESTION_EXTENSION_PATTERN.findall(question or "")}
    attachment_extensions: set[str] = set()
    for attachment in attachments or []:
        payload: dict[str, object] | None = None
        if isinstance(attachment, dict):
            payload = attachment
        elif hasattr(attachment, "model_dump"):
            payload = attachment.model_dump()  # type: ignore[attr-defined]
        elif hasattr(attachment, "dict"):
            payload = attachment.dict()  # type: ignore[attr-defined]
        if not payload:
            continue
        for key in ("name", "path"):
            value = payload.get(key)
            if not isinstance(value, str):
                continue
            suffix = Path(value).suffix.lower()
            if suffix:
                attachment_extensions.add(suffix)
    return question_extensions | attachment_extensions


def _detect_custom_runtime_skills(
    question: str,
    attachments: list[object] | None,
    available_skills: list[SkillEntry] | None,
) -> list[RuntimeSkill]:
    if not available_skills:
        return []
    extension_set = _extensions_for_skill_detection(question, attachments)
    detected: list[RuntimeSkill] = []
    for catalog_skill in available_skills:
        if not catalog_skill.enabled or catalog_skill.source != "custom" or not catalog_skill.storage_path:
            continue
        skill_root = Path(catalog_skill.storage_path) / "contents"
        if not skill_root.exists():
            continue
        try:
            loaded = load_skill_packs(skill_root)
        except Exception:
            continue
        for skill in loaded.skills:
            if skill.matches_question(question) or skill.matches_extensions(extension_set):
                detected.append(skill)
    # Preserve first-seen order and avoid duplicate IDs.
    deduped: list[RuntimeSkill] = []
    seen_ids: set[str] = set()
    for skill in detected:
        if skill.id in seen_ids:
            continue
        seen_ids.add(skill.id)
        deduped.append(skill)
    return deduped


def _filter_enabled_runtime_skills(
    detected_skills: list[RuntimeSkill],
    available_skills: list[SkillEntry] | None = None,
) -> list[RuntimeSkill]:
    if not detected_skills:
        return []
    if available_skills is None:
        return detected_skills
    if not available_skills:
        return []
    enabled_ids = {
        item.skill_id
        for item in available_skills
        if item.enabled and item.skill_id
    }
    if not enabled_ids:
        return []
    return [skill for skill in detected_skills if skill.id in enabled_ids]


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
    def __init__(
        self,
        task_id: str,
        loop: asyncio.AbstractEventLoop,
        step_listener: Callable[[StepEvent, dict[str, Any]], None] | None = None,
    ) -> None:
        self.task_id = task_id
        self.loop = loop
        self.queue: asyncio.Queue[StepEventModel | None] = asyncio.Queue()
        self._step_listener = step_listener

    def emit(self, step: StepEvent, data: dict) -> None:
        artifact_payloads: list[dict[str, Any]] = []
        if step == StepEvent.deactivate_toolkit:
            # Collect artifacts once so they can be persisted and streamed live.
            artifact_payloads = _collect_tool_artifacts(self.task_id, data)
        event = _emit(self.task_id, step, data)
        events: list[tuple[StepEvent, dict[str, Any], StepEventModel]] = [(step, data, event)]
        for artifact_payload in artifact_payloads:
            artifact_event = _emit(self.task_id, StepEvent.artifact, artifact_payload)
            events.append((StepEvent.artifact, artifact_payload, artifact_event))

        def _enqueue() -> None:
            for queued_step, queued_data, queued_event in events:
                if self._step_listener is not None:
                    try:
                        self._step_listener(queued_step, queued_data)
                    except Exception as exc:
                        logger.warning("step_listener_failed: %s", exc)
                self.queue.put_nowait(queued_event)

        if self.loop.is_running():
            self.loop.call_soon_threadsafe(_enqueue)
        else:
            _enqueue()

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
        for spec in agent_specs:
            tools = build_agent_tools(
                spec.tools or [],
                event_stream,
                spec.name,
                str(workdir),
                mcp_tools=mcp_tools,
                search_backend=search_backend,
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
            detected_skills = detect_runtime_skills(action.question, attachments)
            custom_detected_skills = _detect_custom_runtime_skills(
                action.question,
                attachments,
                skill_catalog,
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
            active_skills = _filter_enabled_runtime_skills(
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
