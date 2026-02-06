from enum import StrEnum


class StepEvent(StrEnum):
    confirmed = "confirmed"
    decompose_text = "decompose_text"
    to_sub_tasks = "to_sub_tasks"
    task_state = "task_state"
    create_agent = "create_agent"
    activate_agent = "activate_agent"
    deactivate_agent = "deactivate_agent"
    assign_task = "assign_task"
    activate_toolkit = "activate_toolkit"
    deactivate_toolkit = "deactivate_toolkit"
    streaming = "streaming"
    artifact = "artifact"
    notice = "notice"
    ask_user = "ask_user"
    turn_cancelled = "turn_cancelled"
    end = "end"
    error = "error"
    context_too_long = "context_too_long"
