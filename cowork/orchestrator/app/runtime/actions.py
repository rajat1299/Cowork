from enum import StrEnum
from typing import Union

from pydantic import BaseModel


class ActionType(StrEnum):
    improve = "improve"
    stop = "stop"


class TaskStatus(StrEnum):
    confirming = "confirming"
    processing = "processing"
    done = "done"
    stopped = "stopped"


class AgentSpec(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    tools: list[str] = []


class ActionImprove(BaseModel):
    type: ActionType = ActionType.improve
    project_id: str
    task_id: str
    question: str
    auth_token: str | None = None
    provider_id: int | None = None
    model_provider: str | None = None
    model_type: str | None = None
    api_key: str | None = None
    endpoint_url: str | None = None
    agents: list[AgentSpec] | None = None


class ActionStop(BaseModel):
    type: ActionType = ActionType.stop
    project_id: str
    reason: str | None = None


Action = Union[ActionImprove, ActionStop]
