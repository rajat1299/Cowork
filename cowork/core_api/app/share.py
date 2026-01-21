from datetime import datetime, timedelta

import jwt

from app.config import settings


def create_share_token(task_id: str) -> tuple[str, datetime]:
    expires_at = datetime.utcnow() + timedelta(minutes=settings.share_token_minutes)
    payload = {
        "task_id": task_id,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_share_token(token: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    task_id = payload.get("task_id")
    if not task_id:
        raise ValueError("Invalid share token")
    return task_id
