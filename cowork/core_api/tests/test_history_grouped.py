from __future__ import annotations

from fastapi.testclient import TestClient


def _create_history(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    task_id: str,
    project_id: str,
    question: str,
    project_name: str,
    tokens: int,
    status: int,
) -> dict:
    response = client.post(
        "/chat/history",
        headers=auth_headers,
        json={
            "task_id": task_id,
            "project_id": project_id,
            "question": question,
            "language": "en",
            "model_platform": "openai",
            "model_type": "gpt-4o-mini",
            "project_name": project_name,
            "tokens": tokens,
            "status": status,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_list_grouped_histories_returns_project_aggregates(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    _create_history(
        client,
        auth_headers,
        task_id="task-a1",
        project_id="project-a",
        question="First prompt A",
        project_name="Alpha",
        tokens=10,
        status=2,
    )
    _create_history(
        client,
        auth_headers,
        task_id="task-a2",
        project_id="project-a",
        question="Second prompt A",
        project_name="Alpha",
        tokens=25,
        status=1,
    )
    _create_history(
        client,
        auth_headers,
        task_id="task-b1",
        project_id="project-b",
        question="Only prompt B",
        project_name="Beta",
        tokens=5,
        status=2,
    )

    response = client.get("/chat/histories/grouped?include_tasks=true", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_projects"] == 2
    assert payload["total_tasks"] == 3
    assert payload["total_tokens"] == 40

    projects = {item["project_id"]: item for item in payload["projects"]}
    assert set(projects.keys()) == {"project-a", "project-b"}

    project_a = projects["project-a"]
    assert project_a["project_name"] == "Alpha"
    assert project_a["task_count"] == 2
    assert project_a["total_tokens"] == 35
    assert project_a["total_completed_tasks"] == 1
    assert project_a["total_ongoing_tasks"] == 1
    assert project_a["last_prompt"] == "Second prompt A"
    assert len(project_a["tasks"]) == 2

    project_b = projects["project-b"]
    assert project_b["project_name"] == "Beta"
    assert project_b["task_count"] == 1
    assert project_b["total_tokens"] == 5
    assert project_b["total_completed_tasks"] == 1
    assert project_b["total_ongoing_tasks"] == 0
    assert project_b["last_prompt"] == "Only prompt B"
    assert len(project_b["tasks"]) == 1


def test_list_grouped_histories_supports_excluding_tasks(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    _create_history(
        client,
        auth_headers,
        task_id="task-c1",
        project_id="project-c",
        question="Prompt C",
        project_name="Gamma",
        tokens=3,
        status=2,
    )

    response = client.get("/chat/histories/grouped?include_tasks=false", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_projects"] == 1
    assert payload["total_tasks"] == 1
    assert payload["projects"][0]["tasks"] == []
