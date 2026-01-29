from contextvars import ContextVar

current_process_task_id: ContextVar[str] = ContextVar("process_task_id", default="")
current_agent_name: ContextVar[str] = ContextVar("agent_name", default="")
current_auth_token: ContextVar[str | None] = ContextVar("auth_token", default=None)
current_project_id: ContextVar[str | None] = ContextVar("project_id", default=None)
