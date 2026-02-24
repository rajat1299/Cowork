from typing import Any

from pydantic import BaseModel


INTERACTION_CONTRACT_VERSION = "2026-02-23"


class HealthResponse(BaseModel):
    status: str
    service: str
    env: str


class StepEvent(BaseModel):
    task_id: str
    step: str
    data: Any
    timestamp: float | None = None
    event_id: str | None = None
    idempotency_key: str | None = None
    request_id: str | None = None
    contract_version: str = INTERACTION_CONTRACT_VERSION


class ArtifactEvent(BaseModel):
    task_id: str
    artifact_type: str
    name: str
    content_url: str | None = None
    created_at: float | None = None
    event_id: str | None = None
    idempotency_key: str | None = None
    request_id: str | None = None
    contract_version: str = INTERACTION_CONTRACT_VERSION


class AgentEvent(BaseModel):
    type: str
    payload: Any | None = None
    timestamp_ms: int | None = None
    turn_id: str | None = None
    session_id: str | None = None
    event_id: str | None = None
