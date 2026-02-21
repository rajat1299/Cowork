from __future__ import annotations

from fastapi.testclient import TestClient


def test_oauth_callback_uses_desktop_scheme(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr('app.api.oauth.settings.app_callback_scheme', 'cowork')

    response = client.get('/oauth/google/callback?code=desktop-code&state=desktop-state')

    assert response.status_code == 200
    assert 'cowork://oauth/callback?provider=google&code=desktop-code&state=desktop-state' in response.text


def test_oauth_callback_uses_http_base_url_when_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr('app.api.oauth.settings.app_callback_scheme', 'http://localhost:5173')

    response = client.get('/oauth/github/callback?code=web-code')

    assert response.status_code == 200
    assert 'http://localhost:5173/oauth/callback?provider=github&code=web-code' in response.text
