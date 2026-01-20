from dataclasses import dataclass
from datetime import datetime
import threading

from app.security import create_access_token


@dataclass
class UserRecord:
    id: int
    email: str
    password_hash: str
    created_at: datetime


@dataclass
class TokenRecord:
    token: str
    user_id: int
    created_at: datetime


@dataclass
class ConfigRecord:
    id: int
    user_id: int
    group: str
    name: str
    value: str
    created_at: datetime
    updated_at: datetime


@dataclass
class StepRecord:
    id: int
    task_id: str
    step: str
    data: dict
    timestamp: float | None
    created_at: datetime


_lock = threading.Lock()
_user_id_seq = 0
_config_id_seq = 0
_step_id_seq = 0

_users_by_email: dict[str, UserRecord] = {}
_users_by_id: dict[int, UserRecord] = {}
_tokens: dict[str, TokenRecord] = {}
_configs: dict[int, ConfigRecord] = {}
_steps: list[StepRecord] = []


def create_user(email: str, password_hash: str) -> UserRecord:
    global _user_id_seq
    with _lock:
        if email in _users_by_email:
            raise ValueError("email already registered")
        _user_id_seq += 1
        record = UserRecord(
            id=_user_id_seq,
            email=email,
            password_hash=password_hash,
            created_at=datetime.utcnow(),
        )
        _users_by_email[email] = record
        _users_by_id[record.id] = record
        return record


def get_user_by_email(email: str) -> UserRecord | None:
    return _users_by_email.get(email)


def get_user_by_id(user_id: int) -> UserRecord | None:
    return _users_by_id.get(user_id)


def create_token(user_id: int) -> str:
    token = create_access_token()
    _tokens[token] = TokenRecord(token=token, user_id=user_id, created_at=datetime.utcnow())
    return token


def get_user_by_token(token: str) -> UserRecord | None:
    record = _tokens.get(token)
    if not record:
        return None
    return get_user_by_id(record.user_id)


def list_configs(user_id: int, group: str | None = None) -> list[ConfigRecord]:
    records = [cfg for cfg in _configs.values() if cfg.user_id == user_id]
    if group:
        records = [cfg for cfg in records if cfg.group == group]
    return records


def create_config(user_id: int, group: str, name: str, value: str) -> ConfigRecord:
    global _config_id_seq
    with _lock:
        _config_id_seq += 1
        now = datetime.utcnow()
        record = ConfigRecord(
            id=_config_id_seq,
            user_id=user_id,
            group=group,
            name=name,
            value=value,
            created_at=now,
            updated_at=now,
        )
        _configs[record.id] = record
        return record


def update_config(config_id: int, user_id: int, group: str, name: str, value: str) -> ConfigRecord:
    with _lock:
        record = _configs.get(config_id)
        if not record or record.user_id != user_id:
            raise KeyError("config not found")
        record.group = group
        record.name = name
        record.value = value
        record.updated_at = datetime.utcnow()
        return record


def delete_config(config_id: int, user_id: int) -> None:
    with _lock:
        record = _configs.get(config_id)
        if not record or record.user_id != user_id:
            raise KeyError("config not found")
        del _configs[config_id]


def add_step(task_id: str, step: str, data: dict, timestamp: float | None) -> StepRecord:
    global _step_id_seq
    with _lock:
        _step_id_seq += 1
        record = StepRecord(
            id=_step_id_seq,
            task_id=task_id,
            step=step,
            data=data,
            timestamp=timestamp,
            created_at=datetime.utcnow(),
        )
        _steps.append(record)
        return record


def list_steps(task_id: str | None = None) -> list[StepRecord]:
    if task_id is None:
        return list(_steps)
    return [step for step in _steps if step.task_id == task_id]
