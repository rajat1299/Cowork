from pathlib import Path

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
