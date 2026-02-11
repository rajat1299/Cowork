import json
from pathlib import Path

from app.runtime.skill_engine import RuntimeSkillEngine


def _benchmark_cases() -> list[dict[str, object]]:
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


def test_runtime_skills_parity_benchmark_report():
    engine = RuntimeSkillEngine(mode="on")
    cases = _benchmark_cases()

    trigger_hits = 0
    for case in cases:
        detected_ids = {skill.id for skill in engine.detect(case["prompt"]) }
        expected_ids = set(case["expect"])
        if expected_ids.issubset(detected_ids):
            trigger_hits += 1

    trigger_precision = (trigger_hits / len(cases)) * 100.0
    profile = engine.score_parity_profile()

    weighted_score = (
        trigger_precision * 0.15
        + profile["procedural_depth"] * 0.20
        + profile["tool_orchestration"] * 0.20
        + profile["output_contracts"] * 0.20
        + profile["validation_recovery"] * 0.15
        + profile["observability"] * 0.10
    )

    report = {
        "weighted_score": weighted_score,
        "trigger_precision": trigger_precision,
        "profile": profile,
        "cases": len(cases),
        "threshold": 82,
        "pass": weighted_score >= 82,
    }

    report_path = Path(__file__).resolve().parent / "skill_benchmarks" / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert weighted_score >= 82, report
