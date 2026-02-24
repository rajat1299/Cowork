from __future__ import annotations

import pytest

from app.clients.core_api import ProviderConfig
from app.runtime.memory import _build_context, _compact_context, _context_budget_snapshot
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
    monkeypatch.setenv("COMPACTION_TRIGGER_TOKENS", "80")
    monkeypatch.setenv("MAX_CONTEXT_TOKENS", "100")

    lock = TaskLock(project_id="proj-memory-budget")
    lock.conversation_history = [{"role": "user", "content": "x" * 500}]

    snapshot = _context_budget_snapshot(lock)
    assert snapshot["current_tokens"] > 100
    assert snapshot["should_compact"] is True
    assert snapshot["is_over_limit"] is True
    assert snapshot["compaction_trigger_tokens"] == 80
    assert snapshot["max_context_tokens"] == 100
