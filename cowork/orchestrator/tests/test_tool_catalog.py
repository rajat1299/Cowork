from app.runtime.tool_catalog import (
    normalize_requested_tools,
    search_tools,
    select_tools_for_turn,
)


def test_normalize_requested_tools_applies_aliases_and_dedupes() -> None:
    requested = ["docs", "file_write", "file", "terminal", "terminal_toolkit", "search_past_chats"]
    normalized = normalize_requested_tools(requested)
    assert normalized == ["file", "terminal", "memory_search"]


def test_select_tools_for_turn_limits_deferred_tools_to_minimum_defaults() -> None:
    requested = [f"tool_{index}" for index in range(12)]
    selection = select_tools_for_turn(requested, query="")
    assert len(selection.selected) == 4
    assert len(selection.dropped) == 8


def test_select_tools_for_turn_keeps_query_matched_tool_without_filling_to_max() -> None:
    requested = [
        "tool_alpha",
        "tool_beta",
        "tool_gamma",
        "tool_delta",
        "tool_epsilon",
        "tool_zeta",
        "slack",
        "tool_eta",
        "tool_theta",
        "tool_iota",
        "tool_kappa",
        "tool_lambda",
    ]

    selection = select_tools_for_turn(requested, query="send a slack update to the team")
    assert "slack" in selection.selected
    assert len(selection.selected) < 10
    assert "tool_lambda" in selection.dropped


def test_search_tools_returns_ranked_matches() -> None:
    requested = ["file", "terminal", "search", "browser", "compose_message"]
    ranked = search_tools("research latest web sources", requested, limit=3)
    assert "search" in ranked
    assert "browser" in ranked
