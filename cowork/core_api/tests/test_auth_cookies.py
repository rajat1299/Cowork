from unittest.mock import patch


def test_desktop_cookie_policy_is_lax_and_not_secure():
    """Desktop env should use SameSite=lax and Secure=false for localhost compatibility."""
    with patch("app.api.auth_cookies.settings") as mock_settings:
        from app.api.auth_cookies import _cookie_samesite, _cookie_secure

        mock_settings.app_env = "desktop"
        assert _cookie_secure() is False
        assert _cookie_samesite() == "lax"

        mock_settings.app_env = "production"
        assert _cookie_secure() is True
        assert _cookie_samesite() == "strict"

        mock_settings.app_env = "development"
        assert _cookie_secure() is False
        assert _cookie_samesite() == "lax"


def test_login_sets_auth_cookies(client, test_user):
    response = client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "TestPassw0rd!"},
    )

    assert response.status_code == 200
    assert response.cookies.get("access_token")
    assert response.cookies.get("refresh_token")

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    # In development/desktop mode SameSite is lax; in production it's strict
    assert "SameSite=lax" in set_cookie_header or "SameSite=Lax" in set_cookie_header or \
           "SameSite=strict" in set_cookie_header or "SameSite=Strict" in set_cookie_header


def test_auth_me_accepts_access_token_cookie(client, test_user):
    login_response = client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "TestPassw0rd!"},
    )
    assert login_response.status_code == 200

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["id"] == test_user.id
    assert payload["email"] == test_user.email


def test_refresh_uses_refresh_cookie_when_body_missing(client, test_user):
    login_response = client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "TestPassw0rd!"},
    )
    assert login_response.status_code == 200
    old_refresh = login_response.cookies.get("refresh_token")
    assert old_refresh

    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.cookies.get("access_token")
    assert refresh_response.cookies.get("refresh_token")
    assert refresh_response.cookies.get("refresh_token") != old_refresh


def test_logout_clears_auth_cookies(client, test_user):
    login_response = client.post(
        "/auth/login",
        json={"email": test_user.email, "password": "TestPassw0rd!"},
    )
    assert login_response.status_code == 200

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200

    me_response = client.get("/auth/me")
    assert me_response.status_code == 401
