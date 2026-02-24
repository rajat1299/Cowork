from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

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
_MIN_COMPACTION_SUMMARY_CHARS = 90
_STALE_EDIT_KEEP_RECENT = 8
_INTENT_CRITICAL_LIMIT = 4
_INTENT_CRITICAL_MIN_OVERLAP = 2
_COMPACTION_INTENT_PRESERVE_LIMIT = 2
_LOW_VALUE_TOOL_OUTPUT_MIN_CHARS = 300
_LOW_VALUE_TOOL_OUTPUT_MARKERS = (
    '"results":',
    '"count":',
    '"toolkit_name":',
    '"method_name":',
    "content successfully written to file",
    "command executed successfully",
)
_INTENT_TOKEN_PATTERN = re.compile(r"[a-z0-9]{4,}")
_INTENT_STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "will",
    "what",
    "when",
    "where",
    "which",
    "please",
    "could",
    "would",
    "should",
    "about",
    "into",
    "your",
    "ours",
    "them",
    "they",
    "then",
    "than",
    "need",
    "want",
    "just",
    "also",
    "like",
    "make",
    "finalize",
    "message",
    "messages",
}
_DEFAULT_MEMORY_RETENTION_DAYS = 180
_MIN_MEMORY_RETENTION_DAYS = 1
_MAX_MEMORY_RETENTION_DAYS = 3650
_DEFAULT_MEMORY_AUTO_MIN_CONFIDENCE = 0.72
_DEFAULT_MEMORY_READ_MIN_CONFIDENCE = 0.5
_DEFAULT_MAX_AUTO_NOTES_PER_RUN = 6
_MAX_AUTO_NOTES_PER_RUN = 12
_DEFAULT_MEMORY_POLICY = {
    "allowed_categories": set(GLOBAL_MEMORY_CATEGORIES),
    "retention_days": _DEFAULT_MEMORY_RETENTION_DAYS,
    "min_auto_confidence": _DEFAULT_MEMORY_AUTO_MIN_CONFIDENCE,
    "min_read_confidence": _DEFAULT_MEMORY_READ_MIN_CONFIDENCE,
    "max_auto_notes_per_run": _DEFAULT_MAX_AUTO_NOTES_PER_RUN,
    "auto_write_enabled": True,
}
_SENSITIVE_MEMORY_PATTERNS = (
    re.compile(r"\bsk-[a-zA-Z0-9]{16,}\b"),
    re.compile(r"\bapi[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{10,}", re.IGNORECASE),
    re.compile(r"\bpassword\s*[:=]\s*['\"].+['\"]", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
)


def _config_value(configs: list[dict[str, object]] | None, name: str) -> str | None:
    for item in configs or []:
        key = item.get("key") or item.get("name")
        if str(key or "") != name:
            continue
        value = item.get("value")
        if value is None:
            return None
        return str(value).strip()
    return None


def _config_int(
    configs: list[dict[str, object]] | None,
    name: str,
    default: int,
    *,
    min_value: int,
    max_value: int,
) -> int:
    raw = _config_value(configs, name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def _config_float(
    configs: list[dict[str, object]] | None,
    name: str,
    default: float,
    *,
    min_value: float,
    max_value: float,
) -> float:
    raw = _config_value(configs, name)
    if raw is None:
        return default
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def _config_categories(configs: list[dict[str, object]] | None) -> set[str]:
    raw = _config_value(configs, "MEMORY_ENABLED_CATEGORIES")
    if not raw:
        return set(GLOBAL_MEMORY_CATEGORIES)
    allowed = {
        token.strip().lower()
        for token in raw.split(",")
        if token and token.strip()
    }
    normalized = allowed & GLOBAL_MEMORY_CATEGORIES
    return normalized or set(GLOBAL_MEMORY_CATEGORIES)


def _build_memory_governance_policy(
    memory_configs: list[dict[str, object]] | None,
    *,
    auto_write_enabled: bool = True,
) -> dict[str, object]:
    return {
        "allowed_categories": _config_categories(memory_configs),
        "retention_days": _config_int(
            memory_configs,
            "MEMORY_RETENTION_DAYS",
            _DEFAULT_MEMORY_RETENTION_DAYS,
            min_value=_MIN_MEMORY_RETENTION_DAYS,
            max_value=_MAX_MEMORY_RETENTION_DAYS,
        ),
        "min_auto_confidence": _config_float(
            memory_configs,
            "MEMORY_AUTO_MIN_CONFIDENCE",
            _DEFAULT_MEMORY_AUTO_MIN_CONFIDENCE,
            min_value=0.0,
            max_value=1.0,
        ),
        "min_read_confidence": _config_float(
            memory_configs,
            "MEMORY_READ_MIN_CONFIDENCE",
            _DEFAULT_MEMORY_READ_MIN_CONFIDENCE,
            min_value=0.0,
            max_value=1.0,
        ),
        "max_auto_notes_per_run": _config_int(
            memory_configs,
            "MEMORY_AUTO_MAX_NOTES_PER_RUN",
            _DEFAULT_MAX_AUTO_NOTES_PER_RUN,
            min_value=1,
            max_value=_MAX_AUTO_NOTES_PER_RUN,
        ),
        "auto_write_enabled": bool(auto_write_enabled),
    }


def _coerce_memory_policy(policy: dict[str, object] | None) -> dict[str, object]:
    if not policy:
        return dict(_DEFAULT_MEMORY_POLICY)
    merged = dict(_DEFAULT_MEMORY_POLICY)
    merged.update(policy)
    allowed_categories = merged.get("allowed_categories")
    if not isinstance(allowed_categories, set):
        allowed_categories = set(GLOBAL_MEMORY_CATEGORIES)
    normalized_categories = {
        str(category).strip().lower()
        for category in allowed_categories
        if str(category).strip().lower() in GLOBAL_MEMORY_CATEGORIES
    }
    merged["allowed_categories"] = normalized_categories or set(GLOBAL_MEMORY_CATEGORIES)
    try:
        retention_days = int(merged.get("retention_days") or _DEFAULT_MEMORY_RETENTION_DAYS)
    except (TypeError, ValueError):
        retention_days = _DEFAULT_MEMORY_RETENTION_DAYS
    merged["retention_days"] = max(_MIN_MEMORY_RETENTION_DAYS, min(_MAX_MEMORY_RETENTION_DAYS, retention_days))

    try:
        min_auto_confidence = float(merged.get("min_auto_confidence") or _DEFAULT_MEMORY_AUTO_MIN_CONFIDENCE)
    except (TypeError, ValueError):
        min_auto_confidence = _DEFAULT_MEMORY_AUTO_MIN_CONFIDENCE
    merged["min_auto_confidence"] = max(0.0, min(1.0, min_auto_confidence))

    try:
        min_read_confidence = float(merged.get("min_read_confidence") or _DEFAULT_MEMORY_READ_MIN_CONFIDENCE)
    except (TypeError, ValueError):
        min_read_confidence = _DEFAULT_MEMORY_READ_MIN_CONFIDENCE
    merged["min_read_confidence"] = max(0.0, min(1.0, min_read_confidence))

    try:
        max_auto_notes = int(merged.get("max_auto_notes_per_run") or _DEFAULT_MAX_AUTO_NOTES_PER_RUN)
    except (TypeError, ValueError):
        max_auto_notes = _DEFAULT_MAX_AUTO_NOTES_PER_RUN
    merged["max_auto_notes_per_run"] = max(1, min(_MAX_AUTO_NOTES_PER_RUN, max_auto_notes))
    merged["auto_write_enabled"] = bool(merged.get("auto_write_enabled", True))
    return merged


def _note_confidence(note: dict[str, object], default: float = 1.0) -> float:
    raw = note.get("confidence")
    if raw is None:
        return default
    try:
        confidence = float(raw)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, confidence))


def _apply_memory_read_policy(
    notes: list[dict[str, object]],
    *,
    allowed_categories: set[str],
    min_auto_confidence: float,
) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for note in notes:
        if bool(note.get("auto_generated")):
            category = str(note.get("category") or "").strip().lower()
            if category and category not in allowed_categories:
                continue
            if _note_confidence(note, default=0.0) < min_auto_confidence:
                continue
        filtered.append(note)
    return filtered


def _contains_sensitive_memory(content: str) -> bool:
    text = content.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _SENSITIVE_MEMORY_PATTERNS)


def _memory_expiry_iso(retention_days: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(days=retention_days)
    return expires_at.isoformat()


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


def _content_tokens(text: str) -> set[str]:
    return {
        token
        for token in _INTENT_TOKEN_PATTERN.findall((text or "").lower())
        if token not in _INTENT_STOPWORDS
    }


def _latest_user_intent_tokens(history: list[dict[str, str]]) -> set[str]:
    for entry in reversed(history):
        if str(entry.get("role") or "") != "user":
            continue
        return _content_tokens(str(entry.get("content") or ""))
    return set()


def _entry_key(entry: dict[str, str]) -> tuple[str, str, str]:
    return (
        str(entry.get("role") or ""),
        str(entry.get("content") or ""),
        str(entry.get("timestamp") or ""),
    )


def _dedupe_history(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        key = _entry_key(entry)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _is_low_value_tool_output(entry: dict[str, str]) -> bool:
    if str(entry.get("role") or "") != "assistant":
        return False
    content = str(entry.get("content") or "")
    if len(content) < _LOW_VALUE_TOOL_OUTPUT_MIN_CHARS:
        return False
    lower = content.lower()
    if any(marker in lower for marker in _LOW_VALUE_TOOL_OUTPUT_MARKERS):
        return True
    return lower.startswith("{") and '"results"' in lower


def _select_intent_critical_entries(
    history: list[dict[str, str]],
    intent_tokens: set[str],
    *,
    limit: int,
) -> list[dict[str, str]]:
    if not history or not intent_tokens or limit <= 0:
        return []
    scored: list[tuple[int, int]] = []
    for index, entry in enumerate(history):
        if _is_low_value_tool_output(entry):
            continue
        overlap = len(_content_tokens(str(entry.get("content") or "")) & intent_tokens)
        if overlap < _INTENT_CRITICAL_MIN_OVERLAP:
            continue
        scored.append((overlap, index))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected_indexes = sorted(index for _, index in scored[:limit])
    return [history[index] for index in selected_indexes]


def _apply_context_edit_policy(history: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(history) <= _STALE_EDIT_KEEP_RECENT:
        return list(history)
    cutoff = len(history) - _STALE_EDIT_KEEP_RECENT
    intent_tokens = _latest_user_intent_tokens(history)
    edited: list[dict[str, str]] = []
    for index, entry in enumerate(history):
        if index >= cutoff:
            edited.append(entry)
            continue
        if not _is_low_value_tool_output(entry):
            edited.append(entry)
            continue
        overlap = len(_content_tokens(str(entry.get("content") or "")) & intent_tokens)
        if overlap >= _INTENT_CRITICAL_MIN_OVERLAP:
            edited.append(entry)
    return edited


def _compaction_retained_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(history) <= _COMPACTION_KEEP_LAST:
        return _dedupe_history(history)
    recent = history[-_COMPACTION_KEEP_LAST:]
    older = history[:-_COMPACTION_KEEP_LAST]
    intent_tokens = _latest_user_intent_tokens(history)
    intent = _select_intent_critical_entries(
        older,
        intent_tokens,
        limit=_COMPACTION_INTENT_PRESERVE_LIMIT,
    )
    return _dedupe_history(intent + recent)


def _select_history_window(history: list[dict[str, str]]) -> list[dict[str, str]]:
    edited_history = _apply_context_edit_policy(history)
    if len(edited_history) <= _history_window_size():
        return _dedupe_history(edited_history)

    # Keep strong recency while preserving user-intent-critical slices.
    recent = edited_history[-_history_window_size():]
    users = [item for item in edited_history if item.get("role") == "user"][-4:]
    older = edited_history[:-_history_window_size()]
    intent_tokens = _latest_user_intent_tokens(edited_history)
    intent = _select_intent_critical_entries(older, intent_tokens, limit=_INTENT_CRITICAL_LIMIT)
    return _dedupe_history(users + intent + recent)


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


def _conversation_tokens(
    task_lock: TaskLock,
    *,
    model_name: str | None = None,
    provider_name: str | None = None,
) -> int:
    total_tokens = 0
    if task_lock.thread_summary:
        total_tokens += estimate_text_tokens(
            task_lock.thread_summary,
            model_name=model_name,
            provider_name=provider_name,
        )
    if task_lock.last_task_summary:
        total_tokens += estimate_text_tokens(
            task_lock.last_task_summary,
            model_name=model_name,
            provider_name=provider_name,
        )
    for note in task_lock.memory_notes:
        content = note.get("content", "")
        total_tokens += estimate_text_tokens(
            str(content),
            model_name=model_name,
            provider_name=provider_name,
        )
    for note in task_lock.global_memory_notes:
        content = note.get("content", "")
        total_tokens += estimate_text_tokens(
            str(content),
            model_name=model_name,
            provider_name=provider_name,
        )
    for entry in task_lock.conversation_history:
        content = entry.get("content", "")
        total_tokens += estimate_text_tokens(
            str(content),
            model_name=model_name,
            provider_name=provider_name,
        )
    return total_tokens


def _context_budget_snapshot(
    task_lock: TaskLock,
    *,
    model_name: str | None = None,
    provider_name: str | None = None,
) -> dict[str, int | bool]:
    compaction_trigger_tokens, max_context_tokens = _context_token_thresholds()
    current_tokens = _conversation_tokens(
        task_lock,
        model_name=model_name,
        provider_name=provider_name,
    )
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
    policy: dict[str, object] | None = None,
) -> None:
    effective_policy = _coerce_memory_policy(policy)
    allowed_categories = set(effective_policy["allowed_categories"])
    min_read_confidence = float(effective_policy["min_read_confidence"])
    notes = await fetch_memory_notes(auth_token, project_id)
    task_lock.memory_notes = _apply_memory_read_policy(
        [note.model_dump() for note in notes],
        allowed_categories=allowed_categories,
        min_auto_confidence=min_read_confidence,
    )
    if include_global:
        global_notes = await fetch_memory_notes(auth_token, GLOBAL_USER_CONTEXT)
        task_lock.global_memory_notes = _apply_memory_read_policy(
            [note.model_dump() for note in global_notes],
            allowed_categories=allowed_categories,
            min_auto_confidence=min_read_confidence,
        )
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
    edited_history = _apply_context_edit_policy(task_lock.conversation_history)
    if not edited_history:
        return False
    history_lines = []
    for entry in edited_history:
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
    if len(summary_text) < _MIN_COMPACTION_SUMMARY_CHARS:
        return False
    summary_lc = summary_text.lower()
    section_hits = sum(1 for marker in _COMPACTION_REQUIRED_HEADERS if marker in summary_lc)
    if section_hits < _MIN_COMPACTION_SECTION_HITS:
        # Avoid replacing existing context with low-fidelity compaction output.
        return False
    task_lock.thread_summary = summary_text
    await upsert_thread_summary(auth_token, project_id, summary_text)
    task_lock.conversation_history = _compaction_retained_history(edited_history)
    return True


async def _generate_global_memory_notes(
    task_lock: TaskLock,
    provider: ProviderConfig,
    auth_token: str | None,
    policy: dict[str, object] | None = None,
) -> None:
    if not auth_token or not task_lock.conversation_history:
        return
    effective_policy = _coerce_memory_policy(policy)
    if not bool(effective_policy.get("auto_write_enabled", True)):
        return
    allowed_categories = set(effective_policy["allowed_categories"])
    min_auto_confidence = float(effective_policy["min_auto_confidence"])
    retention_days = int(effective_policy["retention_days"])
    max_auto_notes_per_run = int(effective_policy["max_auto_notes_per_run"])
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
    allowed_categories_text = ", ".join(sorted(allowed_categories))
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
4. **Category allowlist**: Only use categories from this list: `{allowed_categories_text}`.
5. **Format**: Return a JSON array of objects:
   `[{{"category": "work_context", "content": "...", "confidence": 0.0, "reason": "short reason"}}]`.
6. **Confidence**: Use confidence scores in [0.0, 1.0]. Low confidence or uncertain memories should be omitted.
7. If no NEW long-term facts are found, return an empty array `[]`.
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
    created = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        category = str(item.get("category") or "").strip().lower()
        confidence = _note_confidence(item, default=0.0)
        reason = str(item.get("reason") or "").strip()
        if not content:
            continue
        if category not in allowed_categories:
            continue
        if confidence < min_auto_confidence:
            continue
        if _contains_sensitive_memory(content):
            continue
        norm = content.lower()
        if norm in existing_contents or norm in seen:
            continue
        if created >= max_auto_notes_per_run:
            break
        seen.add(norm)
        await create_memory_note(
            auth_token,
            {
                "project_id": GLOBAL_USER_CONTEXT,
                "category": category,
                "content": content,
                "pinned": False,
                "confidence": confidence,
                "auto_generated": True,
                "expires_at": _memory_expiry_iso(retention_days),
                "provenance": {
                    "source": "assistant_auto",
                    "task_id": task_lock.current_task_id,
                    "reason": reason[:240] if reason else "",
                },
            },
        )
        created += 1


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
