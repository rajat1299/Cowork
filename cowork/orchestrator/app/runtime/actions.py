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


class ActionImprove(BaseModel):
    type: ActionType = ActionType.improve
    project_id: str
    task_id: str
    question: str


class ActionStop(BaseModel):
    type: ActionType = ActionType.stop
    project_id: str
    reason: str | None = None


Action = Union[ActionImprove, ActionStop]
