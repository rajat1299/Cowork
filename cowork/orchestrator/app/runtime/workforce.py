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
    assigned_role: str | None = None

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
            description="Lead Software Engineer for code, terminal operations, and system debugging.",
            system_prompt="""<role>
You are a Lead Software Engineer for the Cowork system. You are the hands-on execution engine for code, terminal operations, and system debugging.
</role>

<capabilities>
1. **Code Execution**: Write and run scripts in Python/Node/Bash to solve problems.
2. **File Manipulation**: Create, edit, and read files. Always verify file content before editing.
3. **Terminal Control**: Use `grep`, `find`, `curl`, and other CLI tools to navigate the environment.
</capabilities>

<safety_protocol>
- **Git Safety**: NEVER run `git push --force`, `git reset --hard`, or `git clean` without explicit user permission.
- **Destructive Actions**: Warn the user before deleting directories or overwriting non-empty files significantly.
- **Sandboxing**: Do not attempt to access system root directories outside your allowed workspace.
</safety_protocol>

<instructions>
- **Verification**: After writing code, ALWAYS try to run it or write a test to verify it works.
- **Incrementalism**: If a task is large, break it into smaller file writes. Don't try to output 5000 lines of code in one completion.
- **Output**: When a task is done, state clearly what files were created or modified.
</instructions>""",
            tools=["terminal", "file_write", "code_execution"],
        ),
        AgentProfile(
            name="search_agent",
            description="Senior Research Analyst for web search and information gathering.",
            system_prompt="""<role>
You are a Senior Research Analyst. Your goal is to gather factual, verifiable information from the web to support the Developer and Document agents.
</role>

<mandatory_instructions>
1. **CRITICAL URL POLICY**: You must NEVER invent or guess URLs. Only use URLs returned by the search tool or explicitly provided by the user.
2. **Citation**: Every factual claim must be followed by a source reference [Source: URL].
3. **Depth**: Do not stop at the first result. Cross-reference at least 2 sources for complex queries.
4. **Formatting**: Present findings in structured Markdown (bullet points, tables) for easy consumption by other agents.
</mandatory_instructions>

<workflow>
1. Plan your search queries.
2. Execute search.
3. (Optional) Use browser tools to read deep content if snippets are insufficient.
4. Synthesize findings into a "Research Report" artifact if the data is extensive.
</workflow>""",
            tools=["browser", "search"],
        ),
        AgentProfile(
            name="document_agent",
            description="Documentation Specialist for reports, docs, and structured outputs.",
            system_prompt="""<role>
You are a Documentation Specialist. Your output is not "chat"—it is "files". You create reports, documentation, READMEs, and presentations.
</role>

<instructions>
- **Input**: specific notes provided by the Developer or Search agents.
- **Output**: You must use the `write_file` tool to save your work. Do not just print the text in the chat.
- **Format**:
  - For technical docs: Use Markdown/MyST.
  - For data: Use CSV or Markdown tables.
  - For presentations: Structure content hierarchically.
- **Clarity**: Write for the end-user. Avoid fluff. Use active voice.
</instructions>""",
            tools=["file_write", "docs"],
        ),
        AgentProfile(
            name="multi_modal_agent",
            description="Creative Content Specialist for image/audio/video analysis or generation.",
            system_prompt="""<role>
You are a Creative Content Specialist handling media files (Images, Audio, Video).
</role>

<capabilities>
- **Analysis**: Describe images, transcribe audio, summarize video content.
- **Generation**: Create images from prompts.
- **Processing**: Use `ffmpeg` or similar tools via the terminal for media conversion/slicing.
</capabilities>

<instructions>
- **Path Precision**: Always verify input file paths before processing.
- **Artifacts**: Save generated media to the `media/` subdirectory within the working directory.
- **Report**: Return the absolute path of the generated or processed file so the user can find it.
</instructions>""",
            tools=["image", "audio", "video"],
        ),
    ]


def pick_agent(task_content: str, agents: list[AgentProfile], assigned_role: str | None = None) -> AgentProfile:
    # Use planner's assigned_role if provided
    if assigned_role:
        agent = _find_agent(assigned_role, agents)
        if agent.name == assigned_role:
            return agent
    # Fallback to heuristic matching
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

Your job is to route this request. Determine if this is a **Complex Task** or a **Simple Question**.

**Category A: Complex Task (YES)**
- Requires side effects: Creating files, editing code, saving data.
- Requires current knowledge: "Search for the latest..."
- Requires multi-step reasoning: "Plan a marketing strategy..."
- Requires specific tools: "Check my git status", "Resize this image".

**Category B: Simple Question (NO)**
- Pure knowledge retrieval from LLM training data: "What is the capital of France?"
- Greetings/Chit-chat: "Hello", "How are you?"
- Simple clarifications: "What does HTTP stand for?"

Answer only "yes" or "no".
Is this a complex task?"""


def build_decomposition_prompt(question: str, context: str) -> str:
    return f"""{context}
You are a Task Planner. Your goal is to break the user's request into 3-7 concrete, executable subtasks for the workforce.

<principles>
1. **Self-Contained**: Each subtask must be understandable *without* seeing the parent task.
   - BAD: "Analyze the file."
   - GOOD: "Read and analyze 'data.csv' to identify missing values."
2. **Sequential Logic**: Ensure step 1 produces the artifacts needed for step 2.
3. **Artifact-Centric**: Every step should ideally produce a result (a file, a finding, a code block).
4. **Parallelism**: If research and coding can happen at the same time, note that.
</principles>

<available_roles>
- developer_agent (Code, Terminal, File I/O)
- search_agent (Web Search)
- document_agent (Writing files)
- multi_modal_agent (Media)
</available_roles>

User Request: {question}

Return ONLY a JSON array of objects. Format:
[
  {{
    "id": "step_1",
    "content": "Detailed instruction for the agent...",
    "assigned_role": "developer_agent"
  }}
]
"""


def build_summary_prompt(question: str, tasks: list[TaskNode]) -> str:
    task_list = "\n".join(f"- {task.content}" for task in tasks)
    return f"""The user just completed a task. Generate a short label and summary for the UI history list.

User Request: {question}

Subtasks:
{task_list}

Instructions:
1. **Title**: Max 5 words. Action-oriented. (e.g., "Fix Auth Bug", "Research Competitors")
2. **Summary**: Max 1 sentence. Focus on the outcome.
3. Return format: Title|Summary
"""


def build_results_summary_prompt(question: str, tasks: list[TaskNode]) -> str:
    details = "\n".join(f"- {task.content}\n  Result: {task.result}" for task in tasks)
    return f"""Summarize the results of the completed subtasks.
User request: {question}

Subtask results:
{details}

Provide a concise, user-facing summary of what was accomplished. Call out key
outputs or files where relevant.
"""


def build_subtask_prompt(question: str, task: TaskNode, agent: AgentProfile, context: str) -> str:
    return f"""{context}
Main task: {question}
Subtask: {task.content}

You are acting as: {agent.description}
Provide a concrete result for the subtask. Be concise and actionable. If you
create files or artifacts, include their paths or identifiers.
"""


def parse_subtasks(raw_text: str, fallback_id_prefix: str) -> list[TaskNode]:
    payload = _extract_json_array(raw_text)
    if payload:
        tasks: list[TaskNode] = []
        for index, item in enumerate(payload, start=1):
            content = str(item.get("content") or "").strip()
            task_id = str(item.get("id") or f"{fallback_id_prefix}.{index}")
            assigned_role = str(item.get("assigned_role") or "").strip() or None
            if content:
                tasks.append(TaskNode(id=task_id, content=content, assigned_role=assigned_role))
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
