from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from app.api.auth_cookies import (
    REFRESH_TOKEN_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from app.auth import get_current_user
from app.config import settings
from app.db import get_session
from app.models import RefreshToken, User
from app.security import create_access_token, create_refresh_token, hash_password, verify_password
from shared.ratelimit import SlidingWindowLimiter, ip_key, rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
_auth_limiter = SlidingWindowLimiter(
    max_requests=settings.rate_limit_auth_per_minute,
    window_seconds=60,
)
_auth_rate_limit = rate_limit(_auth_limiter, ip_key("auth"))


class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value:
            raise ValueError("Invalid email format")
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isdigit() for char in value) or not any(char.isalpha() for char in value):
            raise ValueError("Password must contain letters and numbers")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str


@router.post("/register", response_model=UserResponse, dependencies=[Depends(_auth_rate_limit)])
def register(request: RegisterRequest, session: Session = Depends(get_session)) -> UserResponse:
    existing = session.exec(select(User).where(User.email == request.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=request.email, password_hash=hash_password(request.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserResponse(id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_auth_rate_limit)])
def login(
    request: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> TokenResponse:
    user = session.exec(select(User).where(User.email == request.email.strip().lower())).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    refresh = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
    )
    session.add(refresh)
    session.commit()
    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(_auth_rate_limit)])
def refresh(
    response: Response,
    request: RefreshRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE),
    session: Session = Depends(get_session),
) -> TokenResponse:
    refresh_token = (request.refresh_token.strip() if request and request.refresh_token else "") or (
        refresh_token_cookie.strip() if refresh_token_cookie else ""
    )
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    record = session.exec(select(RefreshToken).where(RefreshToken.token == refresh_token)).first()
    if not record:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if record.revoked or expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token = create_access_token(record.user_id)
    new_refresh_token = create_refresh_token()
    record.token = new_refresh_token
    record.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    session.add(record)
    session.commit()
    set_auth_cookies(response, access_token=access_token, refresh_token=new_refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", dependencies=[Depends(_auth_rate_limit)])
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    token = refresh_token.strip() if refresh_token else ""
    if token:
        record = session.exec(select(RefreshToken).where(RefreshToken.token == token)).first()
        if record and not record.revoked:
            record.revoked = True
            session.add(record)
            session.commit()
    clear_auth_cookies(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)
