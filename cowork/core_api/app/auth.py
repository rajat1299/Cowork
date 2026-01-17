from fastapi import Header, HTTPException

from app.storage import get_user_by_token


def get_current_user(authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid access token")
    return user
