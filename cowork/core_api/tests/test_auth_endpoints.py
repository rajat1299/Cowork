from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _register_user(client: TestClient, *, email: str, password: str = "Password123") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def test_register_login_refresh_and_me_flow(client: TestClient) -> None:
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123"

    registered = _register_user(client, email=email, password=password)
    assert registered["email"] == email

    login_response = client.post("/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    refresh_before = login_response.cookies.get("refresh_token")
    assert refresh_before

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["id"] == registered["id"]
    assert me_payload["email"] == email

    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    refresh_after = refresh_response.cookies.get("refresh_token")
    assert refresh_after
    assert refresh_after != refresh_before


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    _register_user(client, email=email)

    duplicate = client.post("/auth/register", json={"email": email, "password": "Password123"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email already registered"
