from __future__ import annotations

import asyncio

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.main import app
from app.runtime.actions import TaskStatus
from app.runtime.manager import get, get_or_create, remove
from shared.schemas import StepEvent as StepEventModel


def _chat_payload(project_id: str = "proj-auth", task_id: str = "task-auth") -> dict[str, str]:
    return {
        "project_id": project_id,
        "task_id": task_id,
        "question": "hello",
    }


def test_start_chat_requires_authorization_header(monkeypatch):
    async def fake_run_task_loop(task_lock):
        task_lock.status = TaskStatus.done
        yield StepEventModel(task_id="task-auth", step="end", data={"ok": True}, timestamp=1.0)

    monkeypatch.setattr(chat_api, "run_task_loop", fake_run_task_loop)

    with TestClient(app) as client:
        response = client.post("/chat", json=_chat_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid authorization header"


def test_improve_chat_requires_authorization_header():
    with TestClient(app) as client:
        response = client.post(
            "/chat/proj-auth/improve",
            json={"task_id": "task-auth", "question": "hello"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid authorization header"


def test_stop_chat_requires_authorization_header():
    with TestClient(app) as client:
        response = client.delete("/chat/proj-auth")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid authorization header"


def test_improve_chat_with_invalid_token_returns_401(monkeypatch):
    from app import auth as auth_module

    async def fake_verify(_authorization: str) -> None:
        raise HTTPException(status_code=401, detail="Invalid access token")

    monkeypatch.setattr(auth_module, "_verify_with_core_api", fake_verify)

    with TestClient(app) as client:
        response = client.post(
            "/chat/proj-auth/improve",
            json={"task_id": "task-auth", "question": "hello"},
            headers={"Authorization": "Bearer bad-token"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_improve_chat_with_valid_token_queues_action(monkeypatch):
    from app import auth as auth_module

    project_id = "proj-auth-valid"

    async def fake_verify(_authorization: str) -> None:
        return None

    monkeypatch.setattr(auth_module, "_verify_with_core_api", fake_verify)

    with TestClient(app) as client:
        response = client.post(
            f"/chat/{project_id}/improve",
            json={"task_id": "task-auth", "question": "hello"},
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    task_lock = get(project_id)
    assert task_lock is not None
    queued_action = task_lock.queue.get_nowait()
    assert queued_action.auth_token == "Bearer valid-token"
    remove(project_id)


def test_start_chat_with_valid_token_streams_events(monkeypatch):
    from app import auth as auth_module

    project_id = "proj-auth-start"

    async def fake_verify(_authorization: str) -> None:
        return None

    async def fake_run_task_loop(task_lock):
        task_lock.status = TaskStatus.done
        yield StepEventModel(task_id="task-auth", step="end", data={"result": "ok"}, timestamp=1.0)

    monkeypatch.setattr(auth_module, "_verify_with_core_api", fake_verify)
    monkeypatch.setattr(chat_api, "run_task_loop", fake_run_task_loop)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json=_chat_payload(project_id=project_id),
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert "\"step\": \"end\"" in response.text


def test_improve_chat_accepts_access_token_cookie(monkeypatch):
    from app import auth as auth_module

    project_id = "proj-auth-cookie"

    async def fake_verify(_authorization: str) -> None:
        return None

    monkeypatch.setattr(auth_module, "_verify_with_core_api", fake_verify)

    with TestClient(app) as client:
        response = client.post(
            f"/chat/{project_id}/improve",
            json={"task_id": "task-auth", "question": "hello"},
            cookies={"access_token": "cookie-token"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    task_lock = get(project_id)
    assert task_lock is not None
    queued_action = task_lock.queue.get_nowait()
    assert queued_action.auth_token == "Bearer cookie-token"
    remove(project_id)


def test_submit_permission_decision_records_response(monkeypatch):
    from app import auth as auth_module

    project_id = "proj-auth-permission"
    request_id = "req-1"

    async def fake_verify(_authorization: str) -> None:
        return None

    monkeypatch.setattr(auth_module, "_verify_with_core_api", fake_verify)

    task_lock = get_or_create(project_id)
    response_queue = asyncio.Queue(maxsize=1)
    task_lock.human_input[request_id] = response_queue

    with TestClient(app) as client:
        response = client.post(
            f"/chat/{project_id}/permission",
            json={"request_id": request_id, "approved": True},
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "recorded"
    assert response_queue.get_nowait() == "approve"
    remove(project_id)


def test_submit_permission_decision_remembers_ask_once_toolkit_when_requested(monkeypatch):
    from app import auth as auth_module

    project_id = "proj-auth-permission-remember"
    request_id = "req-remember"
    toolkit_key = "filetoolkitwithevents"

    async def fake_verify(_authorization: str) -> None:
        return None

    monkeypatch.setattr(auth_module, "_verify_with_core_api", fake_verify)

    task_lock = get_or_create(project_id)
    response_queue = asyncio.Queue(maxsize=1)
    task_lock.human_input[request_id] = response_queue
    task_lock.pending_approval_context[request_id] = {
        "tier": "ask_once",
        "toolkit_key": toolkit_key,
    }

    with TestClient(app) as client:
        response = client.post(
            f"/chat/{project_id}/permission",
            json={"request_id": request_id, "approved": True, "remember": True},
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response_queue.get_nowait() == "approve"
    assert toolkit_key in task_lock.remembered_approvals
    remove(project_id)


def test_submit_permission_decision_does_not_remember_when_disabled(monkeypatch):
    from app import auth as auth_module

    project_id = "proj-auth-permission-no-remember"
    request_id = "req-no-remember"
    toolkit_key = "filetoolkitwithevents"

    async def fake_verify(_authorization: str) -> None:
        return None

    monkeypatch.setattr(auth_module, "_verify_with_core_api", fake_verify)

    task_lock = get_or_create(project_id)
    response_queue = asyncio.Queue(maxsize=1)
    task_lock.human_input[request_id] = response_queue
    task_lock.pending_approval_context[request_id] = {
        "tier": "ask_once",
        "toolkit_key": toolkit_key,
    }

    with TestClient(app) as client:
        response = client.post(
            f"/chat/{project_id}/permission",
            json={"request_id": request_id, "approved": True, "remember": False},
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response_queue.get_nowait() == "approve"
    assert toolkit_key not in task_lock.remembered_approvals
    remove(project_id)
