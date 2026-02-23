from __future__ import annotations

from sqlmodel import select

from app.api import search as search_api
from app.models import Config, SearchUsage


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> dict:
        return self._payload


def test_exa_search_uses_user_connector_key_without_server_usage(
    client,
    db_session,
    test_user,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    db_session.add(
        Config(
            user_id=test_user.id,
            group="search",
            name="EXA_API_KEY",
            value="user-exa-key",
        )
    )
    db_session.commit()

    monkeypatch.setattr(search_api.settings, "exa_api_key", "")
    seen_keys: list[str | None] = []

    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        seen_keys.append(headers.get("x-api-key"))
        return _FakeResponse({"results": [{"title": "ok"}]})

    monkeypatch.setattr(search_api.httpx, "post", _fake_post)

    response = client.post(
        "/search/exa",
        headers=auth_headers,
        json={"query": "latest ai agents"},
    )

    assert response.status_code == 200
    assert seen_keys == ["user-exa-key"]
    usage = db_session.exec(select(SearchUsage).where(SearchUsage.user_id == test_user.id)).all()
    assert usage == []


def test_exa_search_uses_server_key_and_tracks_usage_when_user_key_missing(
    client,
    db_session,
    test_user,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(search_api.settings, "exa_api_key", "server-exa-key")
    seen_keys: list[str | None] = []

    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        seen_keys.append(headers.get("x-api-key"))
        return _FakeResponse({"results": [{"title": "ok"}]})

    monkeypatch.setattr(search_api.httpx, "post", _fake_post)

    response = client.post(
        "/search/exa",
        headers=auth_headers,
        json={"query": "latest ai agents", "num_results": 2},
    )

    assert response.status_code == 200
    assert seen_keys == ["server-exa-key"]
    usage = db_session.exec(select(SearchUsage).where(SearchUsage.user_id == test_user.id)).all()
    assert len(usage) == 1
    assert usage[0].requests_count == 1
    assert usage[0].results_count == 2


def test_exa_search_returns_503_when_no_user_or_server_key(
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(search_api.settings, "exa_api_key", "")

    response = client.post(
        "/search/exa",
        headers=auth_headers,
        json={"query": "latest ai agents"},
    )

    assert response.status_code == 503
    assert "Exa key is not configured" in response.json()["detail"]
