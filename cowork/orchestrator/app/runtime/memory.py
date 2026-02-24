from __future__ import annotations

import json
import os

from app.clients.core_api import (
    ProviderConfig,
    create_memory_note,
    create_message,
    fetch_memory_notes,
    fetch_messages,
    fetch_task_summary,
    fetch_thread_summary,
    upsert_thread_summary,
)
from app.runtime.llm_client import collect_chat_completion, estimate_text_tokens
from app.runtime.task_lock import TaskLock


_COMPACTION_KEEP_LAST = 12
GLOBAL_USER_CONTEXT = "GLOBAL_USER_CONTEXT"
GLOBAL_MEMORY_CATEGORIES = {
    "work_context",
    "personal_context",
    "tech_stack",
    "preferences",
}
_MAX_SECTION_CHARS = 1200
_MAX_NOTE_COUNT_PER_SECTION = 20
_MAX_HISTORY_TURNS = 24
_MIN_COMPACTION_SECTION_HITS = 3
_COMPACTION_REQUIRED_HEADERS = ("goal", "decisions", "outputs", "open questions", "next steps")
_DEFAULT_COMPACTION_TRIGGER_TOKENS = 20000
_DEFAULT_MAX_CONTEXT_TOKENS = 25000


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
    budget = _MAX_SECTION_CHARS
    rendered = 0
    for note in pinned + other:
        if rendered >= _MAX_NOTE_COUNT_PER_SECTION or budget <= 0:
            break
        content = note.get("content", "")
        category = note.get("category", "note")
        label = "pinned" if note.get("pinned") else category
        text = str(content)
        if len(text) > budget:
            text = text[: max(0, budget - 3)].rstrip() + "..."
        budget -= len(text)
        rendered += 1
        lines.append(f"- ({label}) {text}")
    lines.append("")


def _trim_text(value: str, limit: int = _MAX_SECTION_CHARS) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _history_window_size() -> int:
    raw = os.environ.get("CONTEXT_HISTORY_TURNS")
    if not raw:
        return _MAX_HISTORY_TURNS
    try:
        return max(8, int(raw))
    except (TypeError, ValueError):
        return _MAX_HISTORY_TURNS


def _select_history_window(history: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(history) <= _history_window_size():
        return history
    # Keep strong recency while preserving user intent density.
    recent = history[-_history_window_size():]
    users = [item for item in history if item.get("role") == "user"][-4:]
    merged = users + recent
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in merged:
        key = (
            str(entry.get("role") or ""),
            str(entry.get("content") or ""),
            str(entry.get("timestamp") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


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
                _trim_text(task_lock.thread_summary),
                "",
            ]
        )
    if task_lock.last_task_summary:
        lines.extend(
            [
                "=== Task Summary ===",
                _trim_text(task_lock.last_task_summary),
                "",
            ]
        )
    _append_memory_notes(lines, "=== User Preferences ===", task_lock.global_memory_notes)
    _append_memory_notes(lines, "=== Project Context ===", task_lock.memory_notes)
    if not task_lock.conversation_history:
        return "\n".join(lines).strip() + "\n"
    lines.append("=== Previous Conversation ===")
    for entry in _select_history_window(task_lock.conversation_history):
        role = entry.get("role") or "assistant"
        content = _trim_text(str(entry.get("content") or ""), limit=1000)
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


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return default


def _context_token_thresholds() -> tuple[int, int]:
    compaction_trigger_tokens = _int_env(
        "COMPACTION_TRIGGER_TOKENS",
        _DEFAULT_COMPACTION_TRIGGER_TOKENS,
    )
    max_context_tokens = _int_env(
        "MAX_CONTEXT_TOKENS",
        _DEFAULT_MAX_CONTEXT_TOKENS,
    )
    if compaction_trigger_tokens >= max_context_tokens:
        compaction_trigger_tokens = max(1, max_context_tokens - 1)
    return compaction_trigger_tokens, max_context_tokens


def _conversation_tokens(task_lock: TaskLock) -> int:
    total_tokens = 0
    if task_lock.thread_summary:
        total_tokens += estimate_text_tokens(task_lock.thread_summary)
    if task_lock.last_task_summary:
        total_tokens += estimate_text_tokens(task_lock.last_task_summary)
    for note in task_lock.memory_notes:
        content = note.get("content", "")
        total_tokens += estimate_text_tokens(str(content))
    for note in task_lock.global_memory_notes:
        content = note.get("content", "")
        total_tokens += estimate_text_tokens(str(content))
    for entry in task_lock.conversation_history:
        content = entry.get("content", "")
        total_tokens += estimate_text_tokens(str(content))
    return total_tokens


def _context_budget_snapshot(task_lock: TaskLock) -> dict[str, int | bool]:
    compaction_trigger_tokens, max_context_tokens = _context_token_thresholds()
    current_tokens = _conversation_tokens(task_lock)
    remaining_tokens = max(0, max_context_tokens - current_tokens)
    return {
        "current_tokens": current_tokens,
        "compaction_trigger_tokens": compaction_trigger_tokens,
        "max_context_tokens": max_context_tokens,
        "remaining_tokens": remaining_tokens,
        "should_compact": current_tokens > compaction_trigger_tokens,
        "is_over_limit": current_tokens > max_context_tokens,
    }


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
    summary_lc = summary_text.lower()
    section_hits = sum(1 for marker in _COMPACTION_REQUIRED_HEADERS if marker in summary_lc)
    if section_hits < _MIN_COMPACTION_SECTION_HITS:
        # Avoid replacing existing context with low-fidelity compaction output.
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
