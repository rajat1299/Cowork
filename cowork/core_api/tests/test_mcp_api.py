from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_mcp_users_route_is_not_shadowed_by_mcp_id_route(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get("/mcp/users", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []
