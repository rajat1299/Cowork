from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.runtime.file_naming import is_machine_style_filename
from app.runtime.research_pipeline import extract_citations
from app.runtime.skills_schema import RuntimeSkill


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str
    skill_id: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillValidationResult:
    success: bool
    issues: list[ValidationIssue]
    score: float
    expected_contract: dict[str, Any]
    matched_artifacts: list[dict[str, Any]]


def _artifact_extension(artifact: dict[str, Any]) -> str:
    name = str(artifact.get("name") or artifact.get("path") or "")
    return Path(name).suffix.lower()


def _matches_output_contract(skill: RuntimeSkill, artifact: dict[str, Any]) -> bool:
    allowed = [ext.lower() for ext in skill.output_contract.allowed_extensions]
    if not allowed:
        return True
    return _artifact_extension(artifact) in allowed


def _load_transcript_content(transcript: str, artifact: dict[str, Any]) -> str:
    file_path = artifact.get("path")
    if isinstance(file_path, str) and file_path:
        path = Path(file_path)
        if path.exists() and path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                pass
    return transcript


def validate_skill_contract(
    *,
    skill: RuntimeSkill,
    artifacts: list[dict[str, Any]],
    transcript: str,
    explicit_filenames: set[str],
) -> SkillValidationResult:
    issues: list[ValidationIssue] = []
    matched_artifacts = [artifact for artifact in artifacts if _matches_output_contract(skill, artifact)]

    expected_contract = {
        "required_artifact": skill.output_contract.required_artifact,
        "allowed_extensions": list(skill.output_contract.allowed_extensions),
        "minimum_artifacts": skill.output_contract.minimum_artifacts,
        "description": skill.output_contract.description,
    }

    if skill.output_contract.required_artifact:
        minimum = max(skill.output_contract.minimum_artifacts, 1)
        if len(matched_artifacts) < minimum:
            issues.append(
                ValidationIssue(
                    code="artifact_missing",
                    message=(
                        f"Skill '{skill.name}' requires at least {minimum} artifact(s) "
                        f"with extensions {list(skill.output_contract.allowed_extensions)}."
                    ),
                    severity="error",
                    skill_id=skill.id,
                    details={"expected": expected_contract},
                )
            )

    for rule in skill.validation_rules:
        if rule == "require_two_citations":
            citations = extract_citations(transcript)
            if len(citations) < 2:
                issues.append(
                    ValidationIssue(
                        code="citations_insufficient",
                        message="Research output must contain at least two citations.",
                        severity="error",
                        skill_id=skill.id,
                        details={"citation_count": len(citations)},
                    )
                )

        if rule == "markdown_structure" and matched_artifacts:
            markdown_artifact = next(
                (artifact for artifact in matched_artifacts if _artifact_extension(artifact) == ".md"),
                None,
            )
            if markdown_artifact:
                content = _load_transcript_content(transcript, markdown_artifact)
                has_heading = "#" in content
                has_body = len(content.strip()) >= 40
                if not (has_heading and has_body):
                    issues.append(
                        ValidationIssue(
                            code="markdown_structure",
                            message="Markdown artifact should contain headings and substantive body content.",
                            severity="warning",
                            skill_id=skill.id,
                        )
                    )

        if rule == "human_readable_filename":
            for artifact in matched_artifacts:
                name = str(artifact.get("name") or "")
                if not name or name in explicit_filenames:
                    continue
                if is_machine_style_filename(name):
                    issues.append(
                        ValidationIssue(
                            code="filename_style",
                            message=(
                                f"Artifact '{name}' is machine-style. Prefer human-readable naming "
                                "unless user requested exact filename."
                            ),
                            severity="warning",
                            skill_id=skill.id,
                            details={"artifact": name},
                        )
                    )

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    score = max(0.0, 100.0 - (error_count * 18.0) - (warning_count * 6.0))

    return SkillValidationResult(
        success=error_count == 0,
        issues=issues,
        score=score,
        expected_contract=expected_contract,
        matched_artifacts=matched_artifacts,
    )
