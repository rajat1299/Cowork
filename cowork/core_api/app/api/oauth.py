from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.oauth_adapter import get_oauth_adapter
from app.oauth_service import get_or_create_oauth_user, issue_tokens
from app.oauth_state import consume_state, create_state
from app.config import settings
from shared.ratelimit import SlidingWindowLimiter, ip_key, rate_limit

router = APIRouter(prefix="/oauth", tags=["oauth"])
_oauth_limiter = SlidingWindowLimiter(
    max_requests=settings.rate_limit_oauth_per_minute,
    window_seconds=60,
)
_oauth_rate_limit = rate_limit(_oauth_limiter, ip_key("oauth_token"))


class OAuthCallbackPayload(BaseModel):
    code: str
    state: str | None = None
    code_verifier: str | None = None


@router.get("/{provider}/login")
def oauth_login(
    provider: str,
    request: Request,
    state: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
):
    try:
        callback_url = str(request.url_for("oauth_callback", provider=provider))
        adapter = get_oauth_adapter(provider)
        resolved_state = create_state(provider, state)
        return RedirectResponse(
            adapter.get_authorize_url(
                callback_url,
                resolved_state,
                code_challenge,
                code_challenge_method,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{provider}/callback", name="oauth_callback")
def oauth_callback(provider: str, code: str, state: str | None = None):
    redirect_url = f"{settings.app_callback_scheme}://callback/oauth?provider={provider}&code={code}"
    if state:
        redirect_url += f"&state={state}"
    html_content = f"""
    <html>
        <head><title>OAuth Callback</title></head>
        <body>
            <script type='text/javascript'>
                window.location.href = '{redirect_url}';
            </script>
            <p>Redirecting, please wait...</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/{provider}/token", dependencies=[Depends(_oauth_rate_limit)])
def oauth_token(
    provider: str,
    data: OAuthCallbackPayload,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        adapter = get_oauth_adapter(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not consume_state(provider, data.state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    redirect_uri = str(request.url_for("oauth_callback", provider=provider))
    token_data = adapter.exchange_code(data.code, redirect_uri, data.code_verifier)
    profile = adapter.fetch_profile(token_data)
    provider_user_id = profile.get("provider_user_id")
    if not provider_user_id:
        raise HTTPException(status_code=400, detail="Missing provider user id")
    user = get_or_create_oauth_user(
        session,
        provider=provider,
        provider_user_id=provider_user_id,
        email=profile.get("email"),
        name=profile.get("name"),
        avatar_url=profile.get("avatar_url"),
    )
    return issue_tokens(session, user.id)
