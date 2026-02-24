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
    audit_log = "audit_log"
    turn_cancelled = "turn_cancelled"
    compose_message = "compose_message"
    end = "end"
    error = "error"
    context_too_long = "context_too_long"


class ToolHookPhase(StrEnum):
    pre_tool_use = "pre_tool_use"
    post_tool_use = "post_tool_use"
    post_tool_use_failure = "post_tool_use_failure"


class ToolAuditEvent(StrEnum):
    request = "tool_execution_request"
    decision = "tool_execution_decision"
    execution = "tool_execution_started"
    failure = "tool_execution_failure"
    hook = "tool_hook_evaluated"
