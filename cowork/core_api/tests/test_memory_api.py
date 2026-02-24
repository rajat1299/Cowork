from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def test_memory_endpoints_round_trip(client: TestClient, auth_headers: dict[str, str]) -> None:
    project_id = "proj-memory"
    task_id = "task-memory-1"

    thread_upsert = client.put(
        "/memory/thread-summary",
        headers=auth_headers,
        json={"project_id": project_id, "summary": "Thread summary v1"},
    )
    assert thread_upsert.status_code == 200
    assert thread_upsert.json()["summary"] == "Thread summary v1"

    thread_get = client.get(
        f"/memory/thread-summary?project_id={project_id}",
        headers=auth_headers,
    )
    assert thread_get.status_code == 200
    assert thread_get.json()["summary"] == "Thread summary v1"

    task_upsert = client.put(
        "/memory/task-summary",
        headers=auth_headers,
        json={"project_id": project_id, "task_id": task_id, "summary": "Task summary v1"},
    )
    assert task_upsert.status_code == 200
    assert task_upsert.json()["task_id"] == task_id

    note_create = client.post(
        "/memory/notes",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "task_id": task_id,
            "category": "note",
            "content": "Remember this detail",
            "pinned": False,
            "confidence": 0.96,
            "auto_generated": False,
            "provenance": {
                "source": "user_manual",
                "reason": "captured from explicit user preference",
            },
        },
    )
    assert note_create.status_code == 200
    note_payload = note_create.json()
    assert note_payload["confidence"] == 0.96
    assert note_payload["auto_generated"] is False
    assert note_payload["provenance"]["source"] == "user_manual"
    note_id = note_create.json()["id"]

    notes_list = client.get(
        f"/memory/notes?project_id={project_id}",
        headers=auth_headers,
    )
    assert notes_list.status_code == 200
    assert len(notes_list.json()) == 1
    assert notes_list.json()[0]["content"] == "Remember this detail"

    note_update = client.put(
        f"/memory/notes/{note_id}",
        headers=auth_headers,
        json={"pinned": True, "content": "Remember this detail (updated)"},
    )
    assert note_update.status_code == 200
    assert note_update.json()["pinned"] is True
    assert note_update.json()["content"] == "Remember this detail (updated)"

    stats = client.get(
        f"/memory/context-stats?project_id={project_id}",
        headers=auth_headers,
    )
    assert stats.status_code == 200
    stats_payload = stats.json()
    assert stats_payload["note_count"] == 1
    assert stats_payload["pinned_count"] == 1

    clear = client.post(
        "/memory/clear",
        headers=auth_headers,
        json={"project_id": project_id},
    )
    assert clear.status_code == 204

    notes_after_clear = client.get(
        f"/memory/notes?project_id={project_id}",
        headers=auth_headers,
    )
    assert notes_after_clear.status_code == 200
    assert notes_after_clear.json() == []

    thread_missing = client.get(
        f"/memory/thread-summary?project_id={project_id}",
        headers=auth_headers,
    )
    assert thread_missing.status_code == 404

    task_missing = client.get(
        f"/memory/task-summary?task_id={task_id}",
        headers=auth_headers,
    )
    assert task_missing.status_code == 404


def test_memory_notes_exclude_expired_by_default(client: TestClient, auth_headers: dict[str, str]) -> None:
    project_id = "proj-memory-expiry"
    now = datetime.now(timezone.utc)

    expired_create = client.post(
        "/memory/notes",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "category": "work_context",
            "content": "Old transient memory",
            "auto_generated": True,
            "confidence": 0.66,
            "expires_at": (now - timedelta(days=1)).isoformat(),
            "provenance": {"source": "assistant_auto"},
        },
    )
    assert expired_create.status_code == 200

    active_create = client.post(
        "/memory/notes",
        headers=auth_headers,
        json={
            "project_id": project_id,
            "category": "work_context",
            "content": "Still relevant memory",
            "auto_generated": True,
            "confidence": 0.84,
            "expires_at": (now + timedelta(days=3)).isoformat(),
            "provenance": {"source": "assistant_auto"},
        },
    )
    assert active_create.status_code == 200

    notes_list = client.get(
        f"/memory/notes?project_id={project_id}",
        headers=auth_headers,
    )
    assert notes_list.status_code == 200
    payload = notes_list.json()
    assert len(payload) == 1
    assert payload[0]["content"] == "Still relevant memory"

    notes_with_expired = client.get(
        f"/memory/notes?project_id={project_id}&include_expired=true",
        headers=auth_headers,
    )
    assert notes_with_expired.status_code == 200
    content = {item["content"] for item in notes_with_expired.json()}
    assert content == {"Old transient memory", "Still relevant memory"}

    stats = client.get(
        f"/memory/context-stats?project_id={project_id}",
        headers=auth_headers,
    )
    assert stats.status_code == 200
    assert stats.json()["note_count"] == 1
