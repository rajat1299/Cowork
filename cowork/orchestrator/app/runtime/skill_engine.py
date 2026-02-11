from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
import os
import re
import time
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, unquote, urlparse

from shared.schemas import ArtifactEvent

from app.runtime.file_naming import (
    extract_explicit_filenames,
    normalize_filename_for_output,
    suggest_filename,
)
from app.runtime.research_pipeline import dedupe_sources, expand_queries
from app.runtime.skill_validators import SkillValidationResult, validate_skill_contract
from app.runtime.skills_schema import RuntimeSkill, load_skill_packs
from app.runtime.sync import fire_and_forget_artifact


logger = logging.getLogger(__name__)

_FILE_DELIVERABLE_INTENT = re.compile(
    r"\b(create|build|generate|draft|prepare|save|export|write)\b.*\b(file|document|doc|report|deck|slides?|spreadsheet|sheet|pdf|docx|pptx|xlsx)\b",
    re.IGNORECASE,
)
_QUESTION_EXTENSION_PATTERN = re.compile(r"\.[a-zA-Z0-9]{2,8}\b")
_BLOCKED_ARTIFACT_SEGMENTS = {
    ".initial_env",
    ".venv",
    "venv",
    "site-packages",
    "dist-info",
    "__pycache__",
    ".git",
    "node_modules",
}
_BLOCKED_ARTIFACT_METADATA_NAMES = {
    "top_level.txt",
    "entry_points.txt",
    "dependency_links.txt",
    "sources.txt",
    "api_tests.txt",
}


@dataclass
class SkillRunState:
    task_id: str
    project_id: str
    question: str
    context: str
    mode: str
    active_skills: list[RuntimeSkill]
    explicit_filenames: set[str]
    started_at: float = field(default_factory=time.time)
    query_plan: list[str] = field(default_factory=list)
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    transcript_chunks: list[str] = field(default_factory=list)
    checkpoints: list[str] = field(default_factory=list)

    def transcript(self) -> str:
        return "".join(self.transcript_chunks).strip()


@dataclass
class SkillValidationSummary:
    success: bool
    score: float
    issues: list[dict[str, Any]]
    by_skill: dict[str, SkillValidationResult]
    expected_contracts: dict[str, dict[str, Any]]


@dataclass
class SkillRepairOutcome:
    success: bool
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class RuntimeSkillEngine:
    def __init__(self, skillpack_root: Path | None = None, mode: str | None = None) -> None:
        self.skillpack_root = skillpack_root or Path(__file__).resolve().parent / "skillpacks"
        self.mode = (mode or os.environ.get("RUNTIME_SKILLS_V2") or "on").strip().lower()
        self.skills: list[RuntimeSkill] = []
        self.load_errors: list[str] = []
        self.metrics: dict[str, int] = {
            "skill_runs_total": 0,
            "skill_contract_failures_total": 0,
            "skill_repairs_success_total": 0,
        }
        self.reload()

    def reload(self) -> None:
        loaded = load_skill_packs(self.skillpack_root)
        self.skills = loaded.skills
        self.load_errors = loaded.errors
        if self.load_errors:
            for error in self.load_errors:
                logger.warning("skillpack_load_error: %s", error)

    def is_enabled(self) -> bool:
        return self.mode in {"on", "shadow", "1", "true", "yes"}

    def is_shadow(self) -> bool:
        return self.mode == "shadow"

    def detect(
        self,
        question: str,
        attachments: Iterable[object] | None = None,
        context: str = "",
    ) -> list[RuntimeSkill]:
        if not self.is_enabled():
            return []

        question = question or ""
        question_extensions = {ext.lower() for ext in _QUESTION_EXTENSION_PATTERN.findall(question)}
        attachment_extensions = self._extract_extensions_from_attachments(attachments)
        all_extensions = question_extensions | attachment_extensions

        selected: list[RuntimeSkill] = []
        for skill in self.skills:
            if skill.matches_question(question) or skill.matches_extensions(all_extensions):
                selected.append(skill)

        # Keep deterministic ordering by the loaded skillpack order.
        selected_ids = {skill.id for skill in selected}
        return [skill for skill in self.skills if skill.id in selected_ids]

    def prepare_plan(
        self,
        *,
        task_id: str,
        project_id: str,
        question: str,
        context: str,
        active_skills: list[RuntimeSkill],
    ) -> SkillRunState:
        self.metrics["skill_runs_total"] += 1
        query_plan: list[str] = []
        if any("research" in skill.id for skill in active_skills):
            query_plan = expand_queries(question)
        return SkillRunState(
            task_id=task_id,
            project_id=project_id,
            question=question,
            context=context,
            mode=self.mode,
            active_skills=active_skills,
            explicit_filenames=extract_explicit_filenames(question),
            query_plan=query_plan,
        )

    def build_runtime_skill_context(self, active_skills: list[RuntimeSkill]) -> str:
        if not active_skills:
            return ""
        lines = ["", "<active_runtime_skills>", "These runtime skills are active for this turn:"]
        for skill in active_skills:
            lines.append(f"- {skill.name}: {skill.description}")
            lines.append(f"  - Skill ID: {skill.id} v{skill.version}")
            if skill.prompt_instructions:
                for instruction in skill.prompt_instructions:
                    lines.append(f"  - {instruction}")
            if skill.policy_markdown:
                lines.append("  - Follow the procedural policy attached to this skill.")
            if skill.output_contract.required_artifact:
                lines.append(
                    "  - Output contract: create at least "
                    f"{max(1, skill.output_contract.minimum_artifacts)} artifact(s) with extensions "
                    f"{list(skill.output_contract.allowed_extensions)}"
                )
        lines.append("</active_runtime_skills>")
        return "\n".join(lines) + "\n"

    def requires_complex_execution(self, question: str, active_skills: list[RuntimeSkill]) -> bool:
        if any(skill.force_complex for skill in active_skills):
            return True
        if not question:
            return False
        return bool(_FILE_DELIVERABLE_INTENT.search(question))

    def inject_agent_policy(self, agent_specs: list[Any], active_skills: list[RuntimeSkill]) -> None:
        if not active_skills or not agent_specs:
            return
        document_agent = self._find_agent(agent_specs, "document_agent")
        developer_agent = self._find_agent(agent_specs, "developer_agent")
        search_agent = self._find_agent(agent_specs, "search_agent")

        for skill in active_skills:
            if skill.required_tools:
                target = document_agent or developer_agent
                if any("search" in tool for tool in skill.required_tools) and search_agent is not None:
                    target = search_agent
                if target is not None:
                    for tool in skill.required_tools:
                        if tool not in target.tools:
                            target.tools.append(tool)

            if skill.output_contract.required_artifact and document_agent is not None:
                if "file_write" not in document_agent.tools:
                    document_agent.tools.append("file_write")

            target_agent = document_agent or developer_agent
            if target_agent is None:
                continue
            skill_context = self.build_runtime_skill_context([skill]).strip()
            if skill_context and skill_context not in target_agent.system_prompt:
                target_agent.system_prompt = f"{target_agent.system_prompt}\n\n{skill_context}"

    def on_step_event(self, run_state: SkillRunState, step: str, data: dict[str, Any]) -> None:
        if not run_state.active_skills:
            return
        if step in {"activate_toolkit", "deactivate_toolkit"}:
            event = {
                "step": step,
                "toolkit": data.get("toolkit_name") or data.get("toolkit"),
                "method": data.get("method_name") or data.get("method"),
                "message": data.get("message"),
                "timestamp": time.time(),
            }
            toolkit_name = str(event.get("toolkit") or "").lower()
            if step == "deactivate_toolkit" and "search" in toolkit_name:
                message = data.get("message")
                if isinstance(message, str):
                    try:
                        parsed = json.loads(message)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
                        parsed["results"] = dedupe_sources(
                            [item for item in parsed["results"] if isinstance(item, dict)]
                        )
                        event["message"] = json.dumps(parsed)
            run_state.tool_events.append(event)
            if step == "deactivate_toolkit":
                run_state.checkpoints.append("tool_completed")
        elif step == "artifact":
            artifact = {
                "id": data.get("id"),
                "type": data.get("type", "file"),
                "name": data.get("name"),
                "content_url": data.get("content_url"),
                "path": data.get("path"),
                "action": data.get("action", "created"),
            }
            if self._is_blocked_artifact(artifact):
                logger.info(
                    "skill_engine_blocked_artifact task_id=%s project_id=%s artifact=%s",
                    run_state.task_id,
                    run_state.project_id,
                    artifact,
                )
                return
            self._upsert_runtime_artifact(run_state, artifact)
            run_state.checkpoints.append("artifact_detected")
        elif step in {"streaming", "decompose_text"}:
            chunk = data.get("chunk") or data.get("content")
            if isinstance(chunk, str) and chunk:
                run_state.transcript_chunks.append(chunk)
        elif step == "end":
            result = data.get("result")
            if isinstance(result, str) and result:
                run_state.transcript_chunks.append(result)

    def validate_outputs(
        self,
        *,
        run_state: SkillRunState,
        workdir: Path,
        transcript: str,
    ) -> SkillValidationSummary:
        by_skill: dict[str, SkillValidationResult] = {}
        expected_contracts: dict[str, dict[str, Any]] = {}
        aggregated_issues: list[dict[str, Any]] = []

        artifacts = self._merge_runtime_artifacts(run_state, workdir)
        transcript_text = transcript or run_state.transcript()
        if transcript and transcript not in run_state.transcript_chunks:
            run_state.transcript_chunks.append(transcript)

        for skill in run_state.active_skills:
            result = validate_skill_contract(
                skill=skill,
                artifacts=artifacts,
                transcript=transcript_text,
                explicit_filenames=run_state.explicit_filenames,
            )
            by_skill[skill.id] = result
            expected_contracts[skill.id] = result.expected_contract
            for issue in result.issues:
                aggregated_issues.append(
                    {
                        "skill_id": issue.skill_id,
                        "code": issue.code,
                        "severity": issue.severity,
                        "message": issue.message,
                        "details": issue.details,
                    }
                )

        success = all(result.success for result in by_skill.values()) if by_skill else True
        score = 100.0
        if by_skill:
            score = sum(result.score for result in by_skill.values()) / len(by_skill)

        if not success:
            self.metrics["skill_contract_failures_total"] += 1

        return SkillValidationSummary(
            success=success,
            score=score,
            issues=aggregated_issues,
            by_skill=by_skill,
            expected_contracts=expected_contracts,
        )

    def repair_or_fail(
        self,
        *,
        run_state: SkillRunState,
        validation: SkillValidationSummary,
        workdir: Path,
    ) -> SkillRepairOutcome:
        if validation.success:
            return SkillRepairOutcome(success=True)

        repaired_artifacts: list[dict[str, Any]] = []
        notes: list[str] = []

        run_state.artifacts = self._filter_user_artifacts(run_state.artifacts)
        normalized = self._normalize_artifact_names(run_state, list(run_state.artifacts))
        for item in normalized:
            if not any(existing.get("path") == item.get("path") for existing in run_state.artifacts):
                self._upsert_runtime_artifact(run_state, item)
                repaired_artifacts.append(item)

        if any(skill.id == "doc_markdown_v1" for skill in run_state.active_skills):
            has_markdown = any(Path(str(artifact.get("name") or "")).suffix.lower() == ".md" for artifact in run_state.artifacts)
            if not has_markdown:
                fallback = self._repair_markdown_from_transcript(run_state, workdir)
                if fallback:
                    self._upsert_runtime_artifact(run_state, fallback)
                    repaired_artifacts.append(fallback)
                    notes.append("Created markdown fallback artifact from transcript.")

        run_state.artifacts = self._filter_user_artifacts(run_state.artifacts)
        repaired_artifacts = self._filter_user_artifacts(repaired_artifacts)

        if repaired_artifacts:
            self.metrics["skill_repairs_success_total"] += 1
            self._persist_artifacts(run_state.task_id, repaired_artifacts)

        refreshed_validation = self.validate_outputs(
            run_state=run_state,
            workdir=workdir,
            transcript=run_state.transcript(),
        )
        return SkillRepairOutcome(
            success=refreshed_validation.success,
            artifacts=repaired_artifacts,
            notes=notes,
        )

    def score_parity_profile(self) -> dict[str, float]:
        if not self.skills:
            return {
                "trigger_precision": 0.0,
                "procedural_depth": 0.0,
                "tool_orchestration": 0.0,
                "output_contracts": 0.0,
                "validation_recovery": 0.0,
                "observability": 0.0,
                "weighted_score": 0.0,
            }

        trigger_precision = 100.0 if all(skill.trigger_patterns for skill in self.skills) else 70.0
        procedural_depth = 100.0 if all(skill.policy_markdown for skill in self.skills) else 65.0
        tool_orchestration = 100.0 if all(skill.required_tools for skill in self.skills) else 60.0
        output_contracts = 100.0 if all(skill.output_contract.description for skill in self.skills) else 65.0
        validation_recovery = 100.0 if all(skill.validation_rules for skill in self.skills) else 55.0
        observability = 100.0

        weighted = (
            trigger_precision * 0.15
            + procedural_depth * 0.20
            + tool_orchestration * 0.20
            + output_contracts * 0.20
            + validation_recovery * 0.15
            + observability * 0.10
        )
        return {
            "trigger_precision": trigger_precision,
            "procedural_depth": procedural_depth,
            "tool_orchestration": tool_orchestration,
            "output_contracts": output_contracts,
            "validation_recovery": validation_recovery,
            "observability": observability,
            "weighted_score": weighted,
        }

    @staticmethod
    def _extract_extensions_from_attachments(attachments: Iterable[object] | None) -> set[str]:
        if not attachments:
            return set()
        extensions: set[str] = set()
        for attachment in attachments:
            payload: dict[str, Any] | None = None
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

    @staticmethod
    def _find_agent(agent_specs: list[Any], name: str) -> Any | None:
        for spec in agent_specs:
            if getattr(spec, "name", "") == name:
                return spec
        return None

    @staticmethod
    def _filter_user_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered: dict[str, dict[str, Any]] = {}
        for artifact in artifacts:
            if RuntimeSkillEngine._is_blocked_artifact(artifact):
                continue
            dedupe_key = RuntimeSkillEngine._artifact_logical_key(artifact)
            if not dedupe_key:
                continue
            filtered[dedupe_key] = artifact
        return list(filtered.values())

    @staticmethod
    def _artifact_logical_key(artifact: dict[str, Any]) -> str:
        artifact_id = str(artifact.get("id") or "").strip()
        if artifact_id:
            return f"id:{artifact_id}"
        path = str(artifact.get("path") or "").strip()
        content_url = str(artifact.get("content_url") or "").strip()
        name = str(artifact.get("name") or "").strip()
        dedupe_key = path or content_url or name
        return f"path:{dedupe_key}" if dedupe_key else ""

    @staticmethod
    def _upsert_runtime_artifact(run_state: SkillRunState, artifact: dict[str, Any]) -> None:
        key = RuntimeSkillEngine._artifact_logical_key(artifact)
        if not key:
            return
        for index, existing in enumerate(run_state.artifacts):
            if RuntimeSkillEngine._artifact_logical_key(existing) == key:
                merged = {**existing, **artifact}
                run_state.artifacts[index] = merged
                return
        run_state.artifacts.append(artifact)

    @staticmethod
    def _normalize_name_for_denylist(value: str) -> str:
        normalized = re.sub(r"[\s-]+", "_", value.strip().lower())
        return re.sub(r"_+", "_", normalized)

    @staticmethod
    def _metadata_name_blocked(name: str) -> bool:
        if not name:
            return False
        return RuntimeSkillEngine._normalize_name_for_denylist(name) in _BLOCKED_ARTIFACT_METADATA_NAMES

    @staticmethod
    def _decode_candidate(value: str) -> str:
        candidate = value.strip()
        if candidate.lower().startswith("file://"):
            candidate = candidate[7:]
        return unquote(candidate)

    @staticmethod
    def _path_candidates_from_artifact(artifact: dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        for key in ("path", "content_url"):
            value = artifact.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        content_url = artifact.get("content_url")
        if isinstance(content_url, str) and content_url.strip():
            parsed = urlparse(content_url)
            path_values = parse_qs(parsed.query).get("path", [])
            candidates.extend(path_values)
        return candidates

    @staticmethod
    def _has_blocked_segment(path_text: str) -> bool:
        normalized = RuntimeSkillEngine._decode_candidate(path_text)
        normalized = normalized.split("?", 1)[0].split("#", 1)[0].replace("\\", "/")
        segments = [segment.strip().lower() for segment in normalized.split("/") if segment.strip()]
        for segment in segments:
            if segment in _BLOCKED_ARTIFACT_SEGMENTS:
                return True
            if segment.endswith(".dist-info"):
                return True
            if "site-packages" in segment:
                return True
        return False

    @staticmethod
    def _is_blocked_artifact(artifact: dict[str, Any]) -> bool:
        name = str(artifact.get("name") or "").strip()
        if RuntimeSkillEngine._metadata_name_blocked(name):
            return True

        for candidate in RuntimeSkillEngine._path_candidates_from_artifact(artifact):
            if RuntimeSkillEngine._has_blocked_segment(candidate):
                return True
            basename = Path(
                RuntimeSkillEngine._decode_candidate(candidate)
                .split("?", 1)[0]
                .split("#", 1)[0]
                .replace("\\", "/")
            ).name
            if RuntimeSkillEngine._metadata_name_blocked(basename):
                return True
        return False

    @staticmethod
    def _merge_runtime_artifacts(run_state: SkillRunState, _workdir: Path) -> list[dict[str, Any]]:
        return RuntimeSkillEngine._filter_user_artifacts(run_state.artifacts)

    @staticmethod
    def _build_generated_file_url(workdir: Path, file_path: Path) -> str:
        try:
            relative_path = file_path.resolve().relative_to(workdir.resolve())
        except ValueError:
            return str(file_path)
        project_id = workdir.name
        return f"/files/generated/{project_id}/download?path={quote(str(relative_path))}"

    def _normalize_artifact_names(
        self,
        run_state: SkillRunState,
        artifacts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        renamed: list[dict[str, Any]] = []
        for artifact in artifacts:
            if self._is_blocked_artifact(artifact):
                continue
            path_text = artifact.get("path")
            if not isinstance(path_text, str) or not path_text:
                continue
            path = Path(path_text)
            if not path.exists() or not path.is_file():
                continue
            normalized_name = normalize_filename_for_output(path.name, run_state.explicit_filenames)
            if normalized_name == path.name:
                continue
            target = path.with_name(normalized_name)
            if self._is_blocked_artifact({"name": target.name, "path": str(target)}):
                continue
            if target.exists():
                continue
            try:
                path.rename(target)
            except OSError:
                continue
            workdir = target.parent
            while workdir.parent != workdir and workdir.name != run_state.project_id:
                workdir = workdir.parent
            content_url = (
                self._build_generated_file_url(workdir, target)
                if workdir.name == run_state.project_id
                else str(target)
            )
            artifact_id = str(artifact.get("id") or "").strip() or f"artifact-renamed-{abs(hash(str(target)))}"
            renamed.append(
                {
                    "id": artifact_id,
                    "type": artifact.get("type", "file"),
                    "name": target.name,
                    "path": str(target),
                    "content_url": content_url,
                    "action": "modified",
                }
            )
        return renamed

    def _repair_markdown_from_transcript(self, run_state: SkillRunState, workdir: Path) -> dict[str, Any] | None:
        transcript = run_state.transcript()
        if not transcript:
            return None
        filename = suggest_filename(run_state.question, ".md", fallback_stem="Summary")
        normalized_name = normalize_filename_for_output(filename, run_state.explicit_filenames)
        target = workdir / normalized_name
        if self._is_blocked_artifact({"name": target.name, "path": str(target)}):
            return None
        if target.exists():
            return None
        try:
            target.write_text(transcript, encoding="utf-8")
        except OSError:
            return None
        return {
            "id": f"artifact-repair-{abs(hash(str(target)))}",
            "type": "file",
            "name": target.name,
            "path": str(target),
            "content_url": self._build_generated_file_url(workdir, target),
        }

    @staticmethod
    def _persist_artifacts(task_id: str, artifacts: list[dict[str, Any]]) -> None:
        now = time.time()
        for artifact in artifacts:
            if RuntimeSkillEngine._is_blocked_artifact(artifact):
                continue
            action = str(artifact.get("action") or "created").lower()
            if action == "modified":
                continue
            fire_and_forget_artifact(
                ArtifactEvent(
                    task_id=task_id,
                    artifact_type=str(artifact.get("type") or "file"),
                    name=str(artifact.get("name") or "artifact"),
                    content_url=str(artifact.get("content_url") or artifact.get("path") or ""),
                    created_at=now,
                )
            )


def _make_engine() -> RuntimeSkillEngine:
    return RuntimeSkillEngine()


_ENGINE: RuntimeSkillEngine | None = None


def get_runtime_skill_engine() -> RuntimeSkillEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _make_engine()
    return _ENGINE
