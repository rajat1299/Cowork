from pathlib import Path
from datetime import datetime

from app.clients.core_api import SkillEntry
from app.runtime.skill_catalog_matching import (
    catalog_skill_matches_request,
    filter_enabled_runtime_skills,
)
from app.runtime.file_naming import (
    extract_explicit_filenames,
    normalize_filename_for_output,
)
from app.runtime.research_pipeline import should_retry_search
from app.runtime.skill_engine import RuntimeSkillEngine
from app.runtime.skills_schema import load_skill_packs


def test_skillpacks_load_required_domains():
    engine = RuntimeSkillEngine()
    ids = {skill.id for skill in engine.skills}
    assert "research_web_v1" in ids
    assert "doc_markdown_v1" in ids
    assert "doc_docx_v1" in ids
    assert "doc_pdf_v1" in ids
    assert "doc_revision_v1" in ids


def test_detect_skills_by_query_and_extension():
    engine = RuntimeSkillEngine(mode="on")

    docx_query = "Create a polished Word document from this research"
    docx_skills = engine.detect(docx_query)
    assert any(skill.id == "doc_docx_v1" for skill in docx_skills)

    attachment_skills = engine.detect(
        "please revise this",
        attachments=[{"name": "notes.pdf", "path": "/tmp/notes.pdf"}],
    )
    assert any(skill.id == "doc_pdf_v1" or skill.id == "doc_revision_v1" for skill in attachment_skills)


def test_load_skill_packs_rejects_invalid_toml(tmp_path: Path):
    pack_dir = tmp_path / "broken_pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "skill.toml").write_text("id='x'\nname='x'\nversion='1'\n[triggers\n", encoding="utf-8")

    loaded = load_skill_packs(tmp_path)
    assert loaded.skills == []
    assert loaded.errors


def test_filename_normalization_respects_explicit_names():
    explicit = extract_explicit_filenames('Create "report_v1.md" and include citations')
    assert "report_v1.md" in explicit

    normalized_explicit = normalize_filename_for_output("report_v1.md", explicit)
    normalized_implicit = normalize_filename_for_output("AI_Learnings_RAG_and_InstructGPT.md", set())

    assert normalized_explicit == "report_v1.md"
    assert normalized_implicit == "AI Learnings RAG And Instructgpt.md"


def test_markdown_contract_validation_and_repair(tmp_path: Path):
    engine = RuntimeSkillEngine(mode="on")
    skills = engine.detect("Create a markdown report summarizing this topic")
    run_state = engine.prepare_plan(
        task_id="task-1",
        project_id="proj-1",
        question="Create a markdown report summarizing this topic",
        context="",
        active_skills=skills,
    )

    validation_before = engine.validate_outputs(
        run_state=run_state,
        workdir=tmp_path,
        transcript="# Summary\n\nThis is a complete report with findings and references.",
    )
    assert validation_before.success is False

    repair = engine.repair_or_fail(run_state=run_state, validation=validation_before, workdir=tmp_path)
    assert repair.success is True
    assert any(artifact["name"].endswith(".md") for artifact in run_state.artifacts)
    assert all(".initial_env" not in str(artifact.get("path") or "") for artifact in run_state.artifacts)


def test_validate_outputs_filters_blocked_system_artifacts(tmp_path: Path):
    engine = RuntimeSkillEngine(mode="on")
    skills = engine.detect("Create a markdown report summarizing this topic")
    run_state = engine.prepare_plan(
        task_id="task-2",
        project_id="proj-2",
        question="Create a markdown report summarizing this topic",
        context="",
        active_skills=skills,
    )

    good_file = tmp_path / "Llama Research Report.md"
    good_file.write_text("# Llama Research Report\n\nDetailed findings and citations.", encoding="utf-8")

    run_state.artifacts.extend(
        [
            {
                "id": "blocked",
                "type": "file",
                "name": "top_level.txt",
                "path": str(tmp_path / ".initial_env" / "lib" / "python3.10" / "site-packages" / "x.dist-info" / "top_level.txt"),
                "content_url": "/files/generated/proj-2/download?path=.initial_env/lib/python3.10/site-packages/x.dist-info/top_level.txt",
            },
            {
                "id": "good",
                "type": "file",
                "name": good_file.name,
                "path": str(good_file),
                "content_url": f"/files/generated/proj-2/download?path={good_file.name}",
            },
        ]
    )

    merged = engine._merge_runtime_artifacts(run_state, tmp_path)
    assert len(merged) == 1
    assert merged[0]["name"] == "Llama Research Report.md"


def test_normalize_artifact_names_skips_blocked_system_paths(tmp_path: Path):
    engine = RuntimeSkillEngine(mode="on")
    skills = engine.detect("Create a markdown report summarizing this topic")
    run_state = engine.prepare_plan(
        task_id="task-3",
        project_id="proj-3",
        question="Create a markdown report summarizing this topic",
        context="",
        active_skills=skills,
    )

    blocked_file = tmp_path / ".initial_env" / "lib" / "python3.10" / "site-packages" / "pkg-1.0.dist-info" / "top_level.txt"
    blocked_file.parent.mkdir(parents=True, exist_ok=True)
    blocked_file.write_text("pkg", encoding="utf-8")

    renamed = engine._normalize_artifact_names(
        run_state,
        [
            {
                "id": "blocked",
                "type": "file",
                "name": blocked_file.name,
                "path": str(blocked_file),
                "content_url": f"/files/generated/proj-3/download?path=.initial_env/{blocked_file.name}",
            }
        ],
    )

    assert renamed == []
    assert blocked_file.exists()


def test_normalize_artifact_names_preserves_logical_id_with_modified_action(tmp_path: Path):
    engine = RuntimeSkillEngine(mode="on")
    skills = engine.detect("Create a markdown report summarizing this topic")
    run_state = engine.prepare_plan(
        task_id="task-rename",
        project_id="proj-rename",
        question="Create a markdown report summarizing this topic",
        context="",
        active_skills=skills,
    )

    source_file = tmp_path / "AI_Learnings_RAG_and_InstructGPT.md"
    source_file.write_text("# Report\n\ncontent", encoding="utf-8")

    renamed = engine._normalize_artifact_names(
        run_state,
        [
            {
                "id": "artifact-1",
                "type": "file",
                "name": source_file.name,
                "path": str(source_file),
                "content_url": f"/files/generated/proj-rename/download?path={source_file.name}",
            }
        ],
    )

    assert len(renamed) == 1
    assert renamed[0]["id"] == "artifact-1"
    assert renamed[0]["action"] == "modified"
    assert renamed[0]["name"] == "AI Learnings RAG And Instructgpt.md"
    assert not source_file.exists()
    assert (tmp_path / "AI Learnings RAG And Instructgpt.md").exists()


def test_persist_artifacts_skips_modified_updates(monkeypatch):
    captured = []
    monkeypatch.setattr("app.runtime.skill_engine.fire_and_forget_artifact", lambda event: captured.append(event))

    RuntimeSkillEngine._persist_artifacts(
        "task-persist",
        [
            {
                "id": "artifact-2",
                "type": "file",
                "name": "AI_Learnings_RAG_and_InstructGPT.md",
                "content_url": "/files/generated/proj/download?path=AI_Learnings_RAG_and_InstructGPT.md",
                "action": "created",
            },
            {
                "id": "artifact-2",
                "type": "file",
                "name": "AI Learnings RAG And Instructgpt.md",
                "content_url": "/files/generated/proj/download?path=AI%20Learnings%20RAG%20And%20Instructgpt.md",
                "action": "modified",
            },
        ],
    )

    assert len(captured) == 1
    assert captured[0].name == "AI_Learnings_RAG_and_InstructGPT.md"


def test_repair_does_not_discover_existing_workdir_files(tmp_path: Path):
    engine = RuntimeSkillEngine(mode="on")
    skills = engine.detect("Create a markdown report summarizing this topic")
    run_state = engine.prepare_plan(
        task_id="task-4",
        project_id="proj-4",
        question="Create a markdown report summarizing this topic",
        context="",
        active_skills=skills,
    )

    # Pre-existing files in the workdir should not be auto-ingested as repair artifacts.
    (tmp_path / "stale.md").write_text("# Old file\n\nNot created in this run.", encoding="utf-8")
    blocked_file = tmp_path / ".initial_env" / "lib" / "python3.10" / "site-packages" / "pkg-1.0.dist-info" / "entry_points.txt"
    blocked_file.parent.mkdir(parents=True, exist_ok=True)
    blocked_file.write_text("old", encoding="utf-8")

    validation_before = engine.validate_outputs(
        run_state=run_state,
        workdir=tmp_path,
        transcript="# New report\n\nCurrent run transcript content.",
    )
    assert validation_before.success is False

    repair = engine.repair_or_fail(run_state=run_state, validation=validation_before, workdir=tmp_path)
    assert repair.success is True
    assert all("stale.md" != artifact.get("name") for artifact in repair.artifacts)
    assert all(".initial_env" not in str(artifact.get("path") or "") for artifact in repair.artifacts)


def test_research_retry_helper():
    assert should_retry_search({"error": "network"}) is True
    assert should_retry_search({"results": []}) is True
    assert should_retry_search({"results": [{"title": "ok"}]}) is False


def test_mixed_task_detects_research_and_document_skills():
    engine = RuntimeSkillEngine(mode="on")
    skills = engine.detect("Research this topic and create a detailed markdown document with citations")
    skill_ids = {skill.id for skill in skills}
    assert "research_web_v1" in skill_ids
    assert "doc_markdown_v1" in skill_ids


def test_filter_enabled_runtime_skills_blocks_disabled_examples():
    engine = RuntimeSkillEngine(mode="on")
    detected = engine.detect("Please research this topic on the web")
    catalog = [
        SkillEntry(
            skill_id="research_web_v1",
            name="research_web",
            description="Research and web browsing with source checks.",
            source="built_in",
            enabled=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    ]
    filtered = filter_enabled_runtime_skills(detected, catalog)
    assert all(skill.id != "research_web_v1" for skill in filtered)


def test_catalog_skill_matches_request_by_keyword_and_extension():
    entry = SkillEntry(
        skill_id="canvas_design",
        name="canvas-design",
        description="Create visual art in PNG/PDF documents.",
        source="example",
        trigger_keywords=["canvas design", "poster"],
        trigger_extensions=[".png", ".pdf"],
        enabled=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    assert catalog_skill_matches_request(entry, "Create a poster for our launch", set()) is True
    assert catalog_skill_matches_request(entry, "Do something else", {".png"}) is True
    assert catalog_skill_matches_request(entry, "Do something else", {".md"}) is False


def test_catalog_skill_matches_request_allows_custom_without_metadata():
    entry = SkillEntry(
        skill_id="custom_docx_v1",
        name="custom-docx",
        description="Custom skill uploaded before discovery metadata existed.",
        source="custom",
        trigger_keywords=[],
        trigger_extensions=[],
        enabled=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    assert catalog_skill_matches_request(entry, "Unrelated prompt", set()) is True
