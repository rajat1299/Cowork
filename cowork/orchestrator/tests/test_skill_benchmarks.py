import json
from datetime import datetime, timezone
import os
from pathlib import Path

from app.runtime.skill_engine import RuntimeSkillEngine

_SKILL_BENCHMARK_DIR = Path(__file__).resolve().parent / "skill_benchmarks"
_REPORT_PATH = _SKILL_BENCHMARK_DIR / "report.json"
_HISTORY_PATH = _SKILL_BENCHMARK_DIR / "history.json"
_HISTORY_LIMIT = 200
_EMIT_ARTIFACTS_ENV = "SKILL_BENCHMARK_EMIT_ARTIFACTS"
_HIGH_IMPACT_SKILLS = {
    "research_web_v1",
    "doc_markdown_v1",
    "doc_docx_v1",
    "doc_pdf_v1",
    "spreadsheet_v1",
}


def _detection_cases() -> list[dict[str, object]]:
    return [
        {"prompt": "Research RAG architecture and cite sources", "expect": ["research_web_v1"]},
        {"prompt": "Search the web for latest OpenAI announcements", "expect": ["research_web_v1"]},
        {"prompt": "Compare two papers and summarize with references", "expect": ["research_web_v1", "doc_markdown_v1"]},
        {"prompt": "Find benchmarks for OCR models", "expect": ["research_web_v1"]},
        {"prompt": "Look up latest SEC guidance and summarize", "expect": ["research_web_v1", "doc_markdown_v1"]},
        {"prompt": "Investigate competitor pricing and cite links", "expect": ["research_web_v1"]},
        {"prompt": "Browse the web and gather primary sources on RAG", "expect": ["research_web_v1"]},
        {"prompt": "Research and write findings in markdown", "expect": ["research_web_v1", "doc_markdown_v1"]},
        {"prompt": "Create a markdown report from this research", "expect": ["doc_markdown_v1"]},
        {"prompt": "Write project retrospective in markdown", "expect": ["doc_markdown_v1"]},
        {"prompt": "Draft a docx executive summary", "expect": ["doc_docx_v1"]},
        {"prompt": "Create a Microsoft Word file with analysis", "expect": ["doc_docx_v1"]},
        {"prompt": "Generate a PDF brief", "expect": ["doc_pdf_v1"]},
        {"prompt": "Export this as PDF", "expect": ["doc_pdf_v1"]},
        {"prompt": "Revise the existing report and keep style", "expect": ["doc_revision_v1"]},
        {"prompt": "Edit the document with these changes", "expect": ["doc_revision_v1"]},
        {"prompt": "Create an xlsx spreadsheet with formulas", "expect": ["spreadsheet_v1"]},
        {"prompt": "Build an excel sheet from this data", "expect": ["spreadsheet_v1"]},
        {"prompt": "Prepare CSV output with totals", "expect": ["spreadsheet_v1"]},
        {"prompt": "Research then create a DOCX deliverable", "expect": ["research_web_v1", "doc_docx_v1"]},
        {"prompt": "Find sources and generate PDF report", "expect": ["research_web_v1", "doc_pdf_v1"]},
        {"prompt": "Research and revise the attached paper", "expect": ["research_web_v1", "doc_revision_v1"]},
        {"prompt": "Analyze this topic and write markdown doc", "expect": ["research_web_v1", "doc_markdown_v1"]},
        {"prompt": "Search web and produce spreadsheet summary", "expect": ["research_web_v1", "spreadsheet_v1"]},
        {"prompt": "Write a detailed document from findings", "expect": ["doc_markdown_v1"]},
        {"prompt": "Create a report and save as .md", "expect": ["doc_markdown_v1"]},
        {"prompt": "Create a word doc from attached data", "expect": ["doc_docx_v1"]},
        {"prompt": "Need a polished PDF deliverable", "expect": ["doc_pdf_v1"]},
        {"prompt": "Update the doc and preserve structure", "expect": ["doc_revision_v1"]},
        {"prompt": "Produce spreadsheet output for finance metrics", "expect": ["spreadsheet_v1"]},
    ]


def _artifact_payload(path: Path) -> dict[str, str]:
    return {
        "id": f"artifact-{path.stem}",
        "type": "file",
        "name": path.name,
        "path": str(path),
        "content_url": f"/files/generated/proj-bench/download?path={path.name}",
    }


def _env_flag(name: str) -> bool:
    value = (os.environ.get(name) or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def test_runtime_skills_parity_benchmark_report(tmp_path: Path):
    engine = RuntimeSkillEngine(mode="on")
    detection_cases = _detection_cases()
    markdown_path = tmp_path / "Release Report.md"
    markdown_path.write_text(
        "# Release Report\n\nThis document summarizes release outcomes and follow-up actions.",
        encoding="utf-8",
    )
    revision_path = tmp_path / "Revised Report.txt"
    revision_path.write_text(
        "Revised report delivered with structure preserved.",
        encoding="utf-8",
    )

    trigger_hits = 0
    user_overrides = 0
    expected_by_skill: dict[str, int] = {}
    hits_by_skill: dict[str, int] = {}
    detection_details: list[dict[str, object]] = []
    for case in detection_cases:
        detected_ids = {skill.id for skill in engine.detect(case["prompt"]) }
        expected_ids = set(case["expect"])
        missing = sorted(expected_ids - detected_ids)
        extras = sorted(detected_ids - expected_ids)
        override_required = bool(missing or extras)

        if expected_ids.issubset(detected_ids):
            trigger_hits += 1
        if override_required:
            user_overrides += 1

        for skill_id in expected_ids:
            expected_by_skill[skill_id] = expected_by_skill.get(skill_id, 0) + 1
            if skill_id in detected_ids:
                hits_by_skill[skill_id] = hits_by_skill.get(skill_id, 0) + 1

        detection_details.append(
            {
                "prompt": case["prompt"],
                "expected": sorted(expected_ids),
                "detected": sorted(detected_ids),
                "missing": missing,
                "extras": extras,
                "override_required": override_required,
            }
        )

    trigger_precision = (trigger_hits / len(detection_cases)) * 100.0
    user_override_rate = (user_overrides / len(detection_cases)) * 100.0
    per_skill_trigger_recall = {
        skill_id: ((hits_by_skill.get(skill_id, 0) / expected_count) * 100.0)
        for skill_id, expected_count in expected_by_skill.items()
    }

    contract_cases = [
        {
            "id": "markdown_contract_pass",
            "skill_id": "doc_markdown_v1",
            "question": "Create markdown release report",
            "transcript": "# Release Report\n\nThis document summarizes release outcomes and follow-up actions.",
            "artifacts": [_artifact_payload(markdown_path)],
        },
        {
            "id": "markdown_contract_repairable",
            "skill_id": "doc_markdown_v1",
            "question": "Create markdown release report",
            "transcript": "# Draft\n\nThis transcript can be converted into a markdown artifact by repair.",
            "artifacts": [],
        },
        {
            "id": "research_contract_pass",
            "skill_id": "research_web_v1",
            "question": "Research market shift and cite sources",
            "transcript": (
                "Findings are supported by sources. "
                "[Source: https://example.com/a] "
                "Additional validation from [Source: https://example.com/b]"
            ),
            "artifacts": [],
        },
        {
            "id": "research_contract_fail",
            "skill_id": "research_web_v1",
            "question": "Research market shift and cite sources",
            "transcript": "Single-source summary without corroboration.",
            "artifacts": [],
        },
        {
            "id": "revision_contract_pass",
            "skill_id": "doc_revision_v1",
            "question": "Revise the document while preserving structure",
            "transcript": "Revised report delivered with structure preserved.",
            "artifacts": [_artifact_payload(revision_path)],
        },
    ]

    contract_passes = 0
    post_repair_passes = 0
    repair_attempts = 0
    repair_successes = 0
    contract_details: list[dict[str, object]] = []
    skill_index = {skill.id: skill for skill in engine.skills}
    for case in contract_cases:
        skill = skill_index[str(case["skill_id"])]
        run_state = engine.prepare_plan(
            task_id=f"bench-{case['id']}",
            project_id="proj-bench",
            question=str(case["question"]),
            context="",
            active_skills=[skill],
        )
        run_state.artifacts = list(case["artifacts"])

        validation = engine.validate_outputs(
            run_state=run_state,
            workdir=tmp_path,
            transcript=str(case["transcript"]),
        )
        if validation.success:
            contract_passes += 1
            post_repair_passes += 1
            contract_details.append(
                {
                    "case_id": case["id"],
                    "skill_id": case["skill_id"],
                    "status": "pass",
                    "issues": [],
                    "repair_attempted": False,
                    "repair_success": None,
                }
            )
            continue

        repair_attempts += 1
        repair = engine.repair_or_fail(
            run_state=run_state,
            validation=validation,
            workdir=tmp_path,
        )
        if repair.success:
            repair_successes += 1
            post_repair_passes += 1
        contract_details.append(
            {
                "case_id": case["id"],
                "skill_id": case["skill_id"],
                "status": "fail",
                "issues": [issue["code"] for issue in validation.issues],
                "repair_attempted": True,
                "repair_success": repair.success,
            }
        )

    contract_pass_rate = (contract_passes / len(contract_cases)) * 100.0
    post_repair_contract_pass_rate = (post_repair_passes / len(contract_cases)) * 100.0
    repair_rate = (
        (repair_successes / repair_attempts) * 100.0
        if repair_attempts
        else 100.0
    )

    high_impact_gates = {
        skill_id: (per_skill_trigger_recall.get(skill_id, 0.0) >= 85.0)
        for skill_id in sorted(_HIGH_IMPACT_SKILLS)
    }

    profile = engine.score_parity_profile()

    weighted_score = (
        trigger_precision * 0.15
        + contract_pass_rate * 0.15
        + repair_rate * 0.10
        + (100.0 - user_override_rate) * 0.10
        + profile["procedural_depth"] * 0.15
        + profile["tool_orchestration"] * 0.15
        + profile["output_contracts"] * 0.10
        + profile["validation_recovery"] * 0.10
    )

    skill_versions = {skill.id: skill.version for skill in engine.skills}
    report = {
        "weighted_score": weighted_score,
        "trigger_precision": trigger_precision,
        "contract_pass_rate": contract_pass_rate,
        "post_repair_contract_pass_rate": post_repair_contract_pass_rate,
        "repair_rate": repair_rate,
        "user_override_rate": user_override_rate,
        "profile": profile,
        "cases": len(detection_cases),
        "contract_cases": len(contract_cases),
        "per_skill_trigger_recall": per_skill_trigger_recall,
        "high_impact_gates": high_impact_gates,
        "detection_details": detection_details,
        "contract_details": contract_details,
        "skill_versions": skill_versions,
        "threshold": 82,
        "pass": weighted_score >= 82
        and contract_pass_rate >= 55
        and repair_rate >= 40
        and user_override_rate <= 35
        and all(high_impact_gates.values()),
    }

    if _env_flag(_EMIT_ARTIFACTS_ENV):
        _SKILL_BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
        _REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

        history: list[dict[str, object]] = []
        if _HISTORY_PATH.exists():
            try:
                existing = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
                if isinstance(existing, list):
                    history = [item for item in existing if isinstance(item, dict)]
            except json.JSONDecodeError:
                history = []
        history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "weighted_score": weighted_score,
                "trigger_precision": trigger_precision,
                "contract_pass_rate": contract_pass_rate,
                "repair_rate": repair_rate,
                "user_override_rate": user_override_rate,
                "per_skill_trigger_recall": per_skill_trigger_recall,
                "skill_versions": skill_versions,
            }
        )
        _HISTORY_PATH.write_text(
            json.dumps(history[-_HISTORY_LIMIT:], indent=2),
            encoding="utf-8",
        )

    assert report["pass"] is True, report
