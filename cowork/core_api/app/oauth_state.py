from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets
import threading


_STATE_TTL_SECONDS = 600
_lock = threading.Lock()


@dataclass
class OAuthState:
    provider: str
    state: str
    expires_at: datetime


_states: dict[str, OAuthState] = {}


def create_state(provider: str, provided_state: str | None = None) -> str:
    value = provided_state or secrets.token_urlsafe(24)
    with _lock:
        _states[value] = OAuthState(
            provider=provider,
            state=value,
            expires_at=datetime.utcnow() + timedelta(seconds=_STATE_TTL_SECONDS),
        )
    return value


def consume_state(provider: str, state: str | None) -> bool:
    if not state:
        return False
    with _lock:
        record = _states.pop(state, None)
    if not record:
        return False
    if record.provider != provider:
        return False
    if record.expires_at < datetime.utcnow():
        return False
    return True
