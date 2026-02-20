from datetime import datetime, timedelta, timezone
import secrets

from sqlmodel import Session, select

from app.config import settings
from app.models import OAuthAccount, RefreshToken, User
from app.security import create_access_token, hash_password


def _fallback_email(provider: str, provider_user_id: str) -> str:
    return f"{provider}-{provider_user_id}@local.oauth"


def get_or_create_oauth_user(
    session: Session,
    provider: str,
    provider_user_id: str,
    email: str | None,
    name: str | None,
    avatar_url: str | None,
) -> User:
    oauth = session.exec(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    ).first()
    if oauth:
        user = session.exec(select(User).where(User.id == oauth.user_id)).first()
        if user:
            return user

    normalized_email = (email or _fallback_email(provider, provider_user_id)).lower()
    user = session.exec(select(User).where(User.email == normalized_email)).first()
    if not user:
        user = User(email=normalized_email, password_hash=hash_password(secrets.token_urlsafe(16)))
        session.add(user)
        session.commit()
        session.refresh(user)

    if not oauth:
        oauth = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )
        session.add(oauth)
        session.commit()

    return user


def issue_tokens(session: Session, user_id: int) -> dict:
    access_token = create_access_token(user_id)
    refresh_token = secrets.token_urlsafe(32)
    refresh = RefreshToken(
        user_id=user_id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
    )
    session.add(refresh)
    session.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
