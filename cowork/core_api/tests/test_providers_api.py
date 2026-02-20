from __future__ import annotations

from fastapi.testclient import TestClient


def _create_provider(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    provider_name: str,
    model_type: str,
    api_key: str,
    prefer: bool = False,
) -> dict:
    response = client.post(
        "/provider",
        headers=auth_headers,
        json={
            "provider_name": provider_name,
            "model_type": model_type,
            "api_key": api_key,
            "endpoint_url": "",
            "prefer": prefer,
            "is_valid": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_provider_crud_and_prefer_flow(client: TestClient, auth_headers: dict[str, str]) -> None:
    primary = _create_provider(
        client,
        auth_headers,
        provider_name="openai",
        model_type="gpt-4o-mini",
        api_key="sk-primary-1234",
    )
    secondary = _create_provider(
        client,
        auth_headers,
        provider_name="anthropic",
        model_type="claude-3-5-sonnet",
        api_key="sk-secondary-5678",
        prefer=True,
    )

    list_response = client.get("/providers", headers=auth_headers)
    assert list_response.status_code == 200
    providers = {item["id"]: item for item in list_response.json()}
    assert set(providers.keys()) == {primary["id"], secondary["id"]}
    assert providers[secondary["id"]]["prefer"] is True
    assert providers[primary["id"]]["prefer"] is False
    assert providers[primary["id"]]["api_key_set"] is True
    assert providers[primary["id"]]["api_key_last4"] == "1234"
    assert "api_key" not in providers[primary["id"]]

    get_response = client.get(f"/provider/{primary['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["provider_name"] == "openai"

    update_response = client.put(
        f"/provider/{primary['id']}",
        headers=auth_headers,
        json={
            "endpoint_url": "https://example.invalid/v1",
            "prefer": True,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["endpoint_url"] == "https://example.invalid/v1"
    assert update_response.json()["prefer"] is True

    list_after_update = client.get("/providers", headers=auth_headers)
    assert list_after_update.status_code == 200
    updated = {item["id"]: item for item in list_after_update.json()}
    assert updated[primary["id"]]["prefer"] is True
    assert updated[secondary["id"]]["prefer"] is False

    delete_response = client.delete(f"/provider/{secondary['id']}", headers=auth_headers)
    assert delete_response.status_code == 204

    final_list = client.get("/providers", headers=auth_headers)
    assert final_list.status_code == 200
    remaining = final_list.json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == primary["id"]
