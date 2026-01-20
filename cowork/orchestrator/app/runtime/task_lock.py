import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from app.runtime.actions import Action, TaskStatus


@dataclass
class TaskLock:
    project_id: str
    queue: asyncio.Queue[Action] = field(default_factory=asyncio.Queue)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.confirming
    current_task_id: str | None = None

    async def put(self, item: Action) -> None:
        self.last_accessed = datetime.utcnow()
        await self.queue.put(item)

    async def get(self) -> Action:
        self.last_accessed = datetime.utcnow()
        return await self.queue.get()
