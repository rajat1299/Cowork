from fastapi import Depends, Header, HTTPException
from jwt import InvalidTokenError
from sqlmodel import Session, select

from app.db import get_session
from app.models import User
from app.security import decode_access_token


def get_current_user(
    authorization: str | None = Header(None),
    session: Session = Depends(get_session),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid access token")
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid access token")
    return user
