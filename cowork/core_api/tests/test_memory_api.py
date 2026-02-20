from __future__ import annotations

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
        },
    )
    assert note_create.status_code == 200
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
