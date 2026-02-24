from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_step_is_idempotent_when_idempotency_key_reused(client: TestClient) -> None:
    payload = {
        "task_id": "task-step-idem",
        "step": "audit_log",
        "data": {"type": "audit_log", "event_name": "permission_request_emitted"},
        "timestamp": 123.0,
        "event_id": "evt-step-1",
        "idempotency_key": "idem-step-1",
        "request_id": "req-step-1",
        "contract_version": "2026-02-23",
    }
    first = client.post("/chat/steps", json=payload)
    second = client.post("/chat/steps", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_create_artifact_is_idempotent_when_idempotency_key_reused(client: TestClient) -> None:
    payload = {
        "task_id": "task-artifact-idem",
        "artifact_type": "file",
        "name": "report.md",
        "content_url": "/tmp/report.md",
        "created_at": 123.0,
        "event_id": "evt-artifact-1",
        "idempotency_key": "idem-artifact-1",
        "request_id": "req-artifact-1",
        "contract_version": "2026-02-23",
    }
    first = client.post("/chat/artifacts", json=payload)
    second = client.post("/chat/artifacts", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
