from enum import StrEnum


class StepEvent(StrEnum):
    confirmed = "confirmed"
    decompose_text = "decompose_text"
    to_sub_tasks = "to_sub_tasks"
    task_state = "task_state"
    end = "end"
    error = "error"
