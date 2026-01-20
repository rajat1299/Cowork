from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    env: str


class StepEvent(BaseModel):
    task_id: str
    step: str
    data: Any
    timestamp: float | None = None


class ArtifactEvent(BaseModel):
    task_id: str
    artifact_type: str
    name: str
    content_url: str | None = None
    created_at: float | None = None
