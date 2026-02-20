from __future__ import annotations

from fastapi import Response

from app.config import settings

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


def _cookie_secure() -> bool:
    return settings.app_env != "development"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": "strict",
        "path": "/",
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.access_token_minutes * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    common = {
        "httponly": True,
        "secure": _cookie_secure(),
        "samesite": "strict",
        "path": "/",
    }
    response.delete_cookie(ACCESS_TOKEN_COOKIE, **common)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, **common)
