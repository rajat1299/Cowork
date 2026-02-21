from __future__ import annotations

from sqlmodel import Session

from app.models import ChatMessage, User


def test_memory_search_works_with_sqlite_backend(
    client,
    db_session: Session,
    test_user: User,
    auth_headers: dict[str, str],
) -> None:
    db_session.add(
        ChatMessage(
            user_id=test_user.id,
            project_id="project-search",
            task_id="task-search-1",
            role="assistant",
            content="Vector database indexing notes for desktop app",
            message_type="assistant",
        )
    )
    db_session.add(
        ChatMessage(
            user_id=test_user.id,
            project_id="project-search",
            task_id="task-search-2",
            role="assistant",
            content="Unrelated deployment checklist",
            message_type="assistant",
        )
    )
    db_session.commit()

    response = client.get(
        "/memory/search?query=vector&project_id=project-search&limit=10",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    assert payload[0]["project_id"] == "project-search"
    assert "vector" in payload[0]["content"].lower()
