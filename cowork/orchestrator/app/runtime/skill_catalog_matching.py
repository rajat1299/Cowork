from __future__ import annotations

import re
from pathlib import Path

from app.clients.core_api import SkillEntry
from app.runtime.skills_schema import RuntimeSkill

_QUESTION_EXTENSION_PATTERN = re.compile(r"\.[a-zA-Z0-9]{1,8}\b")


def extensions_for_skill_detection(question: str, attachments: list[object] | None) -> set[str]:
    question_extensions = {ext.lower() for ext in _QUESTION_EXTENSION_PATTERN.findall(question or "")}
    attachment_extensions: set[str] = set()
    for attachment in attachments or []:
        payload: dict[str, object] | None = None
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
                attachment_extensions.add(suffix)
    return question_extensions | attachment_extensions


def catalog_skill_matches_request(
    catalog_skill: SkillEntry,
    question: str,
    extension_set: set[str],
) -> bool:
    # Backward compatibility: previously uploaded custom skills may not have
    # discovery metadata yet. Keep them eligible for runtime loading.
    if (
        catalog_skill.source == "custom"
        and not (catalog_skill.trigger_keywords or [])
        and not (catalog_skill.trigger_extensions or [])
    ):
        return True

    question_text = (question or "").lower()
    keyword_match = any(keyword.lower() in question_text for keyword in (catalog_skill.trigger_keywords or []))
    extension_match = any(
        extension.lower() in extension_set for extension in (catalog_skill.trigger_extensions or [])
    )
    return keyword_match or extension_match


def filter_enabled_runtime_skills(
    detected_skills: list[RuntimeSkill],
    available_skills: list[SkillEntry] | None = None,
) -> list[RuntimeSkill]:
    if not detected_skills:
        return []
    if available_skills is None:
        return detected_skills
    if not available_skills:
        return []
    enabled_ids = {
        item.skill_id
        for item in available_skills
        if item.enabled and item.skill_id
    }
    if not enabled_ids:
        return []
    return [skill for skill in detected_skills if skill.id in enabled_ids]
