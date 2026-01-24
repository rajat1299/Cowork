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
    active_agent: str = ""
    stop_requested: bool = False
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    last_task_result: str = ""
    last_task_summary: str = ""
    background_tasks: set[asyncio.Task] = field(default_factory=set)
    human_input: dict[str, asyncio.Queue[str]] = field(default_factory=dict)

    async def put(self, item: Action) -> None:
        self.last_accessed = datetime.utcnow()
        await self.queue.put(item)

    async def get(self) -> Action:
        self.last_accessed = datetime.utcnow()
        return await self.queue.get()

    def add_background_task(self, task: asyncio.Task) -> None:
        self.background_tasks.add(task)
        task.add_done_callback(lambda t: self.background_tasks.discard(t))

    def add_conversation(self, role: str, content: str) -> None:
        self.conversation_history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def request_stop(self) -> None:
        self.stop_requested = True
