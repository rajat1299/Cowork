from fastapi import Header, HTTPException

from app.config import settings


def require_internal_key(x_internal_key: str | None = Header(None, alias="X-Internal-Key")) -> None:
    if not settings.internal_api_key:
        return
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid internal key")
