from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field


@dataclass
class TaskNode:
    id: str
    content: str
    subtasks: list["TaskNode"] = field(default_factory=list)
    state: str = "OPEN"
    result: str = ""
    failure_count: int = 0
    assignee_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "state": self.state,
            "subtasks": [child.to_dict() for child in self.subtasks],
        }


@dataclass
class AgentProfile:
    name: str
    description: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def build_default_agents() -> list[AgentProfile]:
    return [
        AgentProfile(
            name="developer_agent",
            description="Software engineer focused on code, debugging, and implementation.",
            system_prompt="You are a senior software engineer. Produce concrete, correct solutions.",
            tools=["terminal", "file_write", "code_execution"],
        ),
        AgentProfile(
            name="search_agent",
            description="Research specialist focused on web search and information gathering.",
            system_prompt="You are a research analyst. Provide accurate, sourced findings.",
            tools=["browser", "search"],
        ),
        AgentProfile(
            name="document_agent",
            description="Documentation specialist for reports, docs, and structured outputs.",
            system_prompt="You are a documentation specialist. Write clear, structured content.",
            tools=["file_write", "docs"],
        ),
        AgentProfile(
            name="multi_modal_agent",
            description="Media specialist for image/audio/video analysis or generation.",
            system_prompt="You are a multimodal specialist. Handle image/audio/video tasks.",
            tools=["image", "audio", "video"],
        ),
    ]


def pick_agent(task_content: str, agents: list[AgentProfile]) -> AgentProfile:
    content = task_content.lower()
    if any(keyword in content for keyword in ("search", "research", "find", "browse", "lookup")):
        return _find_agent("search_agent", agents)
    if any(keyword in content for keyword in ("report", "document", "summary", "write", "slides", "ppt", "doc")):
        return _find_agent("document_agent", agents)
    if any(keyword in content for keyword in ("image", "audio", "video", "visual", "transcribe", "media")):
        return _find_agent("multi_modal_agent", agents)
    return _find_agent("developer_agent", agents)


def _find_agent(name: str, agents: list[AgentProfile]) -> AgentProfile:
    for agent in agents:
        if agent.name == name:
            return agent
    return agents[0]


def build_complexity_prompt(question: str, context: str) -> str:
    return f"""{context}
User Query: {question}

Determine if this request is a complex task or a simple question.
- Complex task: requires tools, code, files, multi-step work.
- Simple question: can be answered directly.

Answer only "yes" or "no".
Is this a complex task?"""


def build_decomposition_prompt(question: str, context: str) -> str:
    return f"""{context}
You are a task planner. Break the user request into 3-7 concrete subtasks.
Return ONLY a JSON array of objects with fields:
- id (string, short stable id)
- content (string, concise task description)

User request:
{question}
"""


def build_summary_prompt(question: str, tasks: list[TaskNode]) -> str:
    task_list = "\n".join(f"- {task.content}" for task in tasks)
    return f"""Create a short name and summary for this task.
Return format: "Task Name|Summary".

User request:
{question}

Subtasks:
{task_list}
"""


def build_results_summary_prompt(question: str, tasks: list[TaskNode]) -> str:
    details = "\n".join(f"- {task.content}\n  Result: {task.result}" for task in tasks)
    return f"""Summarize the results of the completed subtasks.
User request: {question}

Subtask results:
{details}

Provide a concise, user-facing summary of what was accomplished.
"""


def build_subtask_prompt(question: str, task: TaskNode, agent: AgentProfile, context: str) -> str:
    return f"""{context}
Main task: {question}
Subtask: {task.content}

You are acting as: {agent.description}
Provide a concrete result for the subtask. Be concise and actionable.
"""


def parse_subtasks(raw_text: str, fallback_id_prefix: str) -> list[TaskNode]:
    payload = _extract_json_array(raw_text)
    if payload:
        tasks: list[TaskNode] = []
        for index, item in enumerate(payload, start=1):
            content = str(item.get("content") or "").strip()
            task_id = str(item.get("id") or f"{fallback_id_prefix}.{index}")
            if content:
                tasks.append(TaskNode(id=task_id, content=content))
        if tasks:
            return tasks
    return _fallback_subtasks(raw_text, fallback_id_prefix)


def _extract_json_array(raw_text: str) -> list[dict] | None:
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1)
    elif "```" in cleaned:
        cleaned = cleaned.replace("```json", "").replace("```", "")
    matches = re.search(r"\[[\s\S]*\]", cleaned)
    if not matches:
        return None
    try:
        return json.loads(matches.group(0))
    except json.JSONDecodeError:
        return None


def _fallback_subtasks(raw_text: str, fallback_id_prefix: str) -> list[TaskNode]:
    lines = [line.strip("-* ").strip() for line in raw_text.splitlines() if line.strip()]
    tasks: list[TaskNode] = []
    for index, line in enumerate(lines, start=1):
        if len(line) < 3:
            continue
        tasks.append(TaskNode(id=f"{fallback_id_prefix}.{index}", content=line))
    if tasks:
        return tasks
    return [TaskNode(id=fallback_id_prefix, content="Complete the task end-to-end.")]
