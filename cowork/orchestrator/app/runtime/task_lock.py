import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskLock:
    project_id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)

    async def put(self, item: dict) -> None:
        self.last_accessed = datetime.utcnow()
        await self.queue.put(item)

    async def get(self) -> dict:
        self.last_accessed = datetime.utcnow()
        return await self.queue.get()
