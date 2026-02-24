from __future__ import annotations

import json

import pytest

from app.clients.core_api import ProviderConfig
from app.runtime.memory import (
    _apply_memory_read_policy,
    _build_context,
    _compact_context,
    _context_budget_snapshot,
    _generate_global_memory_notes,
)
from app.runtime.task_lock import TaskLock


def _provider() -> ProviderConfig:
    return ProviderConfig(
        id=1,
        provider_name="openai",
        model_type="gpt-4o-mini",
        api_key="test-key",
        endpoint_url=None,
        prefer=True,
    )


def test_build_context_applies_history_window_and_trimming() -> None:
    lock = TaskLock(project_id="proj-memory")
    lock.thread_summary = "x" * 3000
    lock.last_task_summary = "y" * 2500
    lock.conversation_history = [
        {"role": "user" if idx % 2 == 0 else "assistant", "content": f"message-{idx} " + ("z" * 400)}
        for idx in range(80)
    ]

    context = _build_context(lock)
    assert "=== Thread Summary ===" in context
    assert "=== Task Summary ===" in context
    assert "=== Previous Conversation ===" in context
    assert len(context) < 40000
    # Recent content is retained, old content is trimmed by windowing.
    assert "message-79" in context
    assert "message-0" not in context


@pytest.mark.asyncio
async def test_compact_context_rejects_low_fidelity_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = TaskLock(project_id="proj-memory")
    lock.conversation_history = [
        {"role": "user", "content": "Please prepare release plan."},
        {"role": "assistant", "content": "Sure, I will do it."},
    ]

    async def fake_collect(*_args, **_kwargs):
        return ("short summary without required sections", {"total_tokens": 10})

    async def fake_upsert(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.runtime.memory.collect_chat_completion", fake_collect)
    monkeypatch.setattr("app.runtime.memory.upsert_thread_summary", fake_upsert)

    updated = await _compact_context(lock, _provider(), "Bearer token", "proj-memory")
    assert updated is False


@pytest.mark.asyncio
async def test_compact_context_accepts_structured_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = TaskLock(project_id="proj-memory")
    lock.conversation_history = [
        {"role": "user", "content": f"message-{i}"} for i in range(20)
    ]
    structured = """
Goal: ship production release
Decisions: enforce approvals
Outputs: release checklist
Open Questions: rollout target
Next Steps: run validation suite
""".strip()

    async def fake_collect(*_args, **_kwargs):
        return (structured, {"total_tokens": 10})

    async def fake_upsert(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.runtime.memory.collect_chat_completion", fake_collect)
    monkeypatch.setattr("app.runtime.memory.upsert_thread_summary", fake_upsert)

    updated = await _compact_context(lock, _provider(), "Bearer token", "proj-memory")
    assert updated is True
    assert lock.thread_summary == structured
    assert len(lock.conversation_history) == 12


def test_context_budget_snapshot_uses_token_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPACTION_TRIGGER_TOKENS", "40")
    monkeypatch.setenv("MAX_CONTEXT_TOKENS", "50")

    lock = TaskLock(project_id="proj-memory-budget")
    lock.conversation_history = [{"role": "user", "content": "x" * 500}]

    snapshot = _context_budget_snapshot(lock)
    assert snapshot["current_tokens"] > 50
    assert snapshot["should_compact"] is True
    assert snapshot["is_over_limit"] is True
    assert snapshot["compaction_trigger_tokens"] == 40
    assert snapshot["max_context_tokens"] == 50


def test_build_context_prunes_stale_low_value_tool_output() -> None:
    lock = TaskLock(project_id="proj-memory-prune")
    lock.conversation_history = [
        {
            "role": "assistant",
            "content": '{"results": [' + ('{"title":"x"},' * 80) + '], "count": 80}',
            "timestamp": "2026-02-01T00:00:00+00:00",
        }
    ]
    for idx in range(1, 10):
        role = "user" if idx % 2 == 0 else "assistant"
        lock.conversation_history.append(
            {
                "role": role,
                "content": f"message-{idx}",
                "timestamp": f"2026-02-01T00:00:0{idx}+00:00",
            }
        )

    context = _build_context(lock)
    assert '"count": 80' not in context
    assert "message-9" in context


def test_build_context_preserves_intent_critical_slice_beyond_recent_window() -> None:
    lock = TaskLock(project_id="proj-memory-intent")
    lock.conversation_history = [
        {
            "role": "assistant",
            "content": "Noted: Nimbus release date is 2026-09-01.",
            "timestamp": "2026-02-01T00:00:00+00:00",
        }
    ]
    for idx in range(1, 36):
        role = "user" if idx % 2 == 0 else "assistant"
        lock.conversation_history.append(
            {
                "role": role,
                "content": f"filler-{idx}",
                "timestamp": f"2026-02-01T00:01:{idx:02d}+00:00",
            }
        )
    lock.conversation_history.extend(
        [
            {
                "role": "user",
                "content": "Can you remind me of the Nimbus release date for the announcement?",
                "timestamp": "2026-02-01T00:03:00+00:00",
            },
            {
                "role": "assistant",
                "content": "Working on announcement draft.",
                "timestamp": "2026-02-01T00:03:01+00:00",
            },
        ]
    )

    context = _build_context(lock)
    assert "Nimbus release date is 2026-09-01" in context


@pytest.mark.asyncio
async def test_compact_context_rejects_too_short_structured_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = TaskLock(project_id="proj-memory-short-summary")
    lock.conversation_history = [
        {"role": "user", "content": "Please prepare release plan."},
        {"role": "assistant", "content": "Sure, I will do it."},
    ]
    too_short_structured = """
Goal: x
Decisions: y
Outputs: z
Open Questions: a
Next Steps: b
""".strip()

    async def fake_collect(*_args, **_kwargs):
        return (too_short_structured, {"total_tokens": 10})

    async def fake_upsert(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.runtime.memory.collect_chat_completion", fake_collect)
    monkeypatch.setattr("app.runtime.memory.upsert_thread_summary", fake_upsert)

    updated = await _compact_context(lock, _provider(), "Bearer token", "proj-memory-short-summary")
    assert updated is False


@pytest.mark.asyncio
async def test_compact_context_preserves_intent_critical_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = TaskLock(project_id="proj-memory-compact-intent")
    lock.conversation_history = [
        {"role": "assistant", "content": "Reminder: Nimbus release date is 2026-09-01."},
    ]
    lock.conversation_history.extend(
        {"role": "user" if idx % 2 == 0 else "assistant", "content": f"filler-{idx}"}
        for idx in range(1, 30)
    )
    lock.conversation_history.append(
        {
            "role": "user",
            "content": "Now finalize launch messaging with Nimbus release date details.",
        }
    )
    structured = """
Goal: ship production release messaging for Nimbus
Decisions: include exact date in announcement
Outputs: launch copy and checklist
Open Questions: final approver
Next Steps: publish after review
""".strip()

    async def fake_collect(*_args, **_kwargs):
        return (structured, {"total_tokens": 10})

    async def fake_upsert(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.runtime.memory.collect_chat_completion", fake_collect)
    monkeypatch.setattr("app.runtime.memory.upsert_thread_summary", fake_upsert)

    updated = await _compact_context(lock, _provider(), "Bearer token", "proj-memory-compact-intent")
    assert updated is True
    retained = " ".join(str(item.get("content", "")) for item in lock.conversation_history)
    assert "Nimbus release date is 2026-09-01" in retained


def test_apply_memory_read_policy_enforces_category_and_confidence_filters() -> None:
    notes = [
        {
            "category": "tech_stack",
            "content": "User prefers TypeScript.",
            "auto_generated": True,
            "confidence": 0.9,
        },
        {
            "category": "preferences",
            "content": "Low confidence preference.",
            "auto_generated": True,
            "confidence": 0.2,
        },
        {
            "category": "work_context",
            "content": "Manual memory note.",
            "auto_generated": False,
            "confidence": 0.1,
        },
    ]

    filtered = _apply_memory_read_policy(
        notes,
        allowed_categories={"tech_stack", "work_context"},
        min_auto_confidence=0.6,
    )

    assert [item["content"] for item in filtered] == [
        "User prefers TypeScript.",
        "Manual memory note.",
    ]


@pytest.mark.asyncio
async def test_generate_global_memory_notes_applies_governance_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = TaskLock(project_id="proj-memory-governance")
    lock.current_task_id = "task-memory-governance"
    lock.conversation_history = [
        {"role": "user", "content": "I prefer TypeScript for backend services."},
        {"role": "assistant", "content": "Noted. I will remember that preference."},
    ]

    async def fake_fetch_memory_notes(*_args, **_kwargs):
        return []

    async def fake_collect_chat_completion(*_args, **_kwargs):
        payload = [
            {
                "category": "tech_stack",
                "content": "User prefers TypeScript for backend work.",
                "confidence": 0.91,
                "reason": "Repeated preference",
            },
            {
                "category": "preferences",
                "content": "api_key=sk-secret-token",
                "confidence": 0.95,
            },
            {
                "category": "work_context",
                "content": "Low confidence one-off detail.",
                "confidence": 0.33,
            },
            {
                "category": "personal_context",
                "content": "User works in PST timezone.",
                "confidence": 0.82,
            },
        ]
        return (json.dumps(payload), {"total_tokens": 12})

    created_payloads: list[dict[str, object]] = []

    async def fake_create_memory_note(_auth_header, payload):
        created_payloads.append(payload)
        return None

    monkeypatch.setattr("app.runtime.memory.fetch_memory_notes", fake_fetch_memory_notes)
    monkeypatch.setattr("app.runtime.memory.collect_chat_completion", fake_collect_chat_completion)
    monkeypatch.setattr("app.runtime.memory.create_memory_note", fake_create_memory_note)

    await _generate_global_memory_notes(
        lock,
        _provider(),
        "Bearer token",
        policy={
            "allowed_categories": {"tech_stack", "personal_context"},
            "min_auto_confidence": 0.7,
            "retention_days": 30,
            "max_auto_notes_per_run": 4,
        },
    )

    assert len(created_payloads) == 2
    categories = {str(item["category"]) for item in created_payloads}
    assert categories == {"tech_stack", "personal_context"}
    for payload in created_payloads:
        assert payload["auto_generated"] is True
        assert float(payload["confidence"]) >= 0.7
        provenance = payload.get("provenance")
        assert isinstance(provenance, dict)
        assert provenance.get("source") == "assistant_auto"
        assert provenance.get("task_id") == "task-memory-governance"
        assert payload.get("expires_at")
