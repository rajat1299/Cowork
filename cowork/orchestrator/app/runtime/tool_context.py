from contextvars import ContextVar

current_process_task_id: ContextVar[str] = ContextVar("process_task_id", default="")
current_agent_name: ContextVar[str] = ContextVar("agent_name", default="")
