from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from app.runtime.workforce import AgentProfile


@dataclass(frozen=True)
class RuntimeSkill:
    name: str
    description: str
    trigger_patterns: tuple[str, ...] = ()
    file_extensions: tuple[str, ...] = ()
    force_complex: bool = False
    prompt_instructions: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    _compiled_patterns: tuple[re.Pattern[str], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_compiled_patterns",
            tuple(re.compile(pattern, re.IGNORECASE) for pattern in self.trigger_patterns),
        )

    def matches_question(self, question: str) -> bool:
        if not question:
            return False
        return any(pattern.search(question) for pattern in self._compiled_patterns)

    def matches_extensions(self, extensions: Iterable[str]) -> bool:
        normalized = {ext.lower() for ext in extensions if ext}
        return any(ext in normalized for ext in self.file_extensions)


_RUNTIME_SKILLS: tuple[RuntimeSkill, ...] = (
    RuntimeSkill(
        name="docx",
        description="Word document creation and editing",
        trigger_patterns=(
            r"\b(docx|word doc(?:ument)?|microsoft word)\b",
            r"\b(create|write|draft|generate)\s+(?:a\s+)?(?:docx|word document)\b",
        ),
        file_extensions=(".docx", ".doc"),
        force_complex=True,
        prompt_instructions=(
            "If the user asks for a Word deliverable, produce a .docx output file in the project workdir.",
            "Do not stop at chat text when a document file is requested.",
            "Prefer human-readable document filenames; avoid snake_case unless the user requests a specific filename.",
        ),
        required_tools=("file_write", "terminal", "docs"),
    ),
    RuntimeSkill(
        name="pdf",
        description="PDF creation and processing",
        trigger_patterns=(
            r"\b(pdf|portable document format)\b",
            r"\b(extract|merge|split|rotate|create|generate)\s+(?:a\s+)?pdf\b",
        ),
        file_extensions=(".pdf",),
        force_complex=True,
        prompt_instructions=(
            "When PDF output is requested, generate an actual .pdf file and report the saved path.",
            "Prefer human-readable PDF filenames; avoid snake_case unless explicitly requested.",
        ),
        required_tools=("file_write", "terminal"),
    ),
    RuntimeSkill(
        name="xlsx",
        description="Spreadsheet creation and editing",
        trigger_patterns=(
            r"\b(xlsx|xlsm|spreadsheet|excel|csv|tsv)\b",
            r"\b(create|build|update|clean|analyze)\s+(?:an?\s+)?(?:excel|spreadsheet)\b",
        ),
        file_extensions=(".xlsx", ".xlsm", ".csv", ".tsv"),
        force_complex=True,
        prompt_instructions=(
            "For spreadsheet deliverables, write an actual workbook file and ensure formulas are used for derived values.",
            "Return the final spreadsheet file path in the tool output.",
            "Prefer human-readable spreadsheet filenames; avoid snake_case unless explicitly requested.",
        ),
        required_tools=("excel", "file_write", "terminal"),
    ),
    RuntimeSkill(
        name="pptx",
        description="Presentation deck creation and editing",
        trigger_patterns=(
            r"\b(pptx|slides?|deck|presentation)\b",
            r"\b(create|build|prepare|draft)\s+(?:a\s+)?(?:slide deck|presentation)\b",
        ),
        file_extensions=(".pptx",),
        force_complex=True,
        prompt_instructions=(
            "When slides are requested, produce a .pptx file instead of only markdown or chat output.",
            "Keep slide structure clear and ready to open in presentation tools.",
            "Prefer human-readable deck filenames; avoid snake_case unless explicitly requested.",
        ),
        required_tools=("pptx", "file_write", "terminal"),
    ),
)


_QUESTION_EXTENSION_PATTERN = re.compile(r"\.[a-zA-Z0-9]{2,5}\b")
_FILE_DELIVERABLE_INTENT = re.compile(
    r"\b(create|build|generate|draft|prepare|save|export|write)\b.*\b(file|document|doc|report|deck|slides?|spreadsheet|sheet|pdf|docx|pptx|xlsx)\b",
    re.IGNORECASE,
)


def _extract_extensions_from_attachments(attachments: Sequence[object] | None) -> set[str]:
    if not attachments:
        return set()
    extensions: set[str] = set()
    for attachment in attachments:
        payload: dict | None = None
        if isinstance(attachment, dict):
            payload = attachment
        elif hasattr(attachment, "model_dump"):
            payload = attachment.model_dump()  # type: ignore[attr-defined]
        elif hasattr(attachment, "dict"):
            payload = attachment.dict()  # type: ignore[attr-defined]
        if not payload:
            continue
        for key in ("name", "path"):
            value = payload.get(key)
            if not isinstance(value, str):
                continue
            suffix = Path(value).suffix.lower()
            if suffix:
                extensions.add(suffix)
    return extensions


def detect_runtime_skills(question: str, attachments: Sequence[object] | None = None) -> list[RuntimeSkill]:
    question = question or ""
    question_extensions = {ext.lower() for ext in _QUESTION_EXTENSION_PATTERN.findall(question)}
    attachment_extensions = _extract_extensions_from_attachments(attachments)
    all_extensions = question_extensions | attachment_extensions

    selected: list[RuntimeSkill] = []
    for skill in _RUNTIME_SKILLS:
        if skill.matches_question(question) or skill.matches_extensions(all_extensions):
            selected.append(skill)
    return selected


def requires_complex_execution(question: str, active_skills: Sequence[RuntimeSkill]) -> bool:
    if any(skill.force_complex for skill in active_skills):
        return True
    if not question:
        return False
    return bool(_FILE_DELIVERABLE_INTENT.search(question))


def build_runtime_skill_context(active_skills: Sequence[RuntimeSkill]) -> str:
    if not active_skills:
        return ""
    lines = [
        "",
        "<active_runtime_skills>",
        "These runtime skills are active for this turn:",
    ]
    for skill in active_skills:
        lines.append(f"- {skill.name}: {skill.description}")
        for instruction in skill.prompt_instructions:
            lines.append(f"  - {instruction}")
    lines.append("</active_runtime_skills>")
    return "\n".join(lines) + "\n"


def apply_runtime_skills(agent_specs: list[AgentProfile], active_skills: Sequence[RuntimeSkill]) -> None:
    if not agent_specs or not active_skills:
        return

    document_agent = _find_agent(agent_specs, "document_agent")
    developer_agent = _find_agent(agent_specs, "developer_agent")

    for skill in active_skills:
        target = document_agent or developer_agent
        if target is None:
            continue

        for tool in skill.required_tools:
            _ensure_tool(target, tool)

        # These tools are safe defaults for file-producing workflows.
        _ensure_tool(target, "file_write")
        if "terminal" in skill.required_tools:
            _ensure_tool(target, "terminal")

        skill_prompt = build_runtime_skill_context([skill]).strip()
        if skill_prompt and skill_prompt not in target.system_prompt:
            target.system_prompt = f"{target.system_prompt}\n\n{skill_prompt}"


def skill_names(active_skills: Sequence[RuntimeSkill]) -> list[str]:
    return [skill.name for skill in active_skills]


def _find_agent(agent_specs: list[AgentProfile], name: str) -> AgentProfile | None:
    for spec in agent_specs:
        if spec.name == name:
            return spec
    return None


def _ensure_tool(agent: AgentProfile, tool_name: str) -> None:
    if tool_name not in agent.tools:
        agent.tools.append(tool_name)
