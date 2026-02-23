from app.runtime.context import _parse_summary
from app.runtime.workforce import TaskNode, build_summary_prompt


def test_parse_summary_strips_markdown_from_title_and_summary() -> None:
    title, summary = _parse_summary(
        "### 1. **Fix _Auth_ Bug**|> Completed `login` flow and removed markdown noise."
    )

    assert title == "Fix Auth Bug"
    assert summary == "Completed login flow and removed markdown noise."


def test_parse_summary_truncates_long_titles() -> None:
    raw_title = "#" + ("A" * 80)
    title, summary = _parse_summary(f"{raw_title}|Short summary")

    assert title is not None
    assert len(title) == 60
    assert title.endswith("...")
    assert summary == "Short summary"


def test_build_summary_prompt_enforces_plain_text_contract() -> None:
    prompt = build_summary_prompt(
        question="Investigate auth regressions",
        tasks=[TaskNode(id="step_1", content="Trace login failures and summarize impact")],
    )

    assert "Plain text only" in prompt
    assert "Return EXACTLY this format: Title|Summary" in prompt
    assert "Do NOT include numbering" in prompt
