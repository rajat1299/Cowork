from enum import StrEnum


class StepEvent(StrEnum):
    confirmed = "confirmed"
    decompose_text = "decompose_text"
    to_sub_tasks = "to_sub_tasks"
    task_state = "task_state"
    activate_toolkit = "activate_toolkit"
    deactivate_toolkit = "deactivate_toolkit"
    streaming = "streaming"
    artifact = "artifact"
    end = "end"
    error = "error"
