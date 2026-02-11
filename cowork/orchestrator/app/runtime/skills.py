from __future__ import annotations

from typing import Sequence

from app.runtime.skill_engine import RuntimeSkillEngine, get_runtime_skill_engine
from app.runtime.skills_schema import RuntimeSkill
from app.runtime.workforce import AgentProfile


def _engine() -> RuntimeSkillEngine:
    return get_runtime_skill_engine()


def detect_runtime_skills(question: str, attachments: Sequence[object] | None = None) -> list[RuntimeSkill]:
    return _engine().detect(question, attachments)


def requires_complex_execution(question: str, active_skills: Sequence[RuntimeSkill]) -> bool:
    return _engine().requires_complex_execution(question, list(active_skills))


def build_runtime_skill_context(active_skills: Sequence[RuntimeSkill]) -> str:
    return _engine().build_runtime_skill_context(list(active_skills))


def apply_runtime_skills(agent_specs: list[AgentProfile], active_skills: Sequence[RuntimeSkill]) -> None:
    _engine().inject_agent_policy(agent_specs, list(active_skills))


def skill_names(active_skills: Sequence[RuntimeSkill]) -> list[str]:
    return [skill.name for skill in active_skills]


def skill_ids(active_skills: Sequence[RuntimeSkill]) -> list[str]:
    return [skill.id for skill in active_skills]
