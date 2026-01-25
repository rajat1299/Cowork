"""Runtime entrypoint for SSE task processing."""

from app.runtime.camel_runtime import run_task_loop

__all__ = ["run_task_loop"]
