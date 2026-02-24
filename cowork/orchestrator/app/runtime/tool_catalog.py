from __future__ import annotations

from dataclasses import dataclass

from app.runtime.toolkits.camel_tools import TOOL_ALIASES


@dataclass(frozen=True)
class ToolCatalogEntry:
    name: str
    description: str
    keywords: tuple[str, ...]
    args: tuple[str, ...]
    deferred: bool = True


@dataclass(frozen=True)
class ToolSelection:
    selected: list[str]
    dropped: list[str]
    matched: list[str]


_TOOL_CATALOG: dict[str, ToolCatalogEntry] = {
    "terminal": ToolCatalogEntry(
        name="terminal",
        description="Run shell commands inside the workspace.",
        keywords=("terminal", "shell", "command", "bash", "cli"),
        args=("command", "id", "block", "timeout"),
        deferred=False,
    ),
    "file": ToolCatalogEntry(
        name="file",
        description="Read and modify files in the workspace.",
        keywords=("file", "write", "edit", "read", "create", "delete"),
        args=("path", "content"),
        deferred=False,
    ),
    "file_write": ToolCatalogEntry(
        name="file_write",
        description="Create or update files in the workspace.",
        keywords=("file", "write", "edit", "document", "create"),
        args=("path", "content"),
        deferred=False,
    ),
    "docs": ToolCatalogEntry(
        name="docs",
        description="Documentation-oriented file operations.",
        keywords=("docs", "documentation", "report", "markdown"),
        args=("path", "content"),
        deferred=False,
    ),
    "code_execution": ToolCatalogEntry(
        name="code_execution",
        description="Execute code snippets in an isolated subprocess.",
        keywords=("python", "script", "run code", "execute", "program"),
        args=("code", "language"),
        deferred=False,
    ),
    "search": ToolCatalogEntry(
        name="search",
        description="Search the web for recent or factual information.",
        keywords=("search", "web", "latest", "news", "lookup", "find"),
        args=("query", "num_results"),
        deferred=False,
    ),
    "browser": ToolCatalogEntry(
        name="browser",
        description="Open and inspect web pages.",
        keywords=("browser", "web", "open url", "scrape", "read page"),
        args=("url",),
        deferred=True,
    ),
    "memory_search": ToolCatalogEntry(
        name="memory_search",
        description="Search previous chat history and memory notes.",
        keywords=("memory", "history", "past", "previous"),
        args=("query", "project_id", "task_id"),
        deferred=True,
    ),
    "compose_message": ToolCatalogEntry(
        name="compose_message",
        description="Render a communication draft widget in the UI.",
        keywords=("email", "draft", "compose", "message", "slack", "linkedin"),
        args=("body", "subject", "platform", "label", "recipient"),
        deferred=True,
    ),
    "mcp": ToolCatalogEntry(
        name="mcp",
        description="Invoke external MCP-provided tools.",
        keywords=("mcp", "connector", "integration", "external tool"),
        args=("tool", "arguments"),
        deferred=True,
    ),
}


def _tokenize(text: str) -> set[str]:
    return {token for token in (text or "").lower().replace("_", " ").split() if token}


def normalize_tool_name(name: str) -> str:
    normalized = (name or "").strip().lower()
    if not normalized:
        return ""
    return TOOL_ALIASES.get(normalized, normalized)


def normalize_requested_tools(tool_names: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_name in tool_names or []:
        resolved = normalize_tool_name(raw_name)
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        normalized.append(resolved)
    return normalized


def describe_tool(name: str) -> ToolCatalogEntry:
    normalized = normalize_tool_name(name)
    entry = _TOOL_CATALOG.get(normalized)
    if entry is not None:
        return entry
    return ToolCatalogEntry(
        name=normalized,
        description=f"{normalized} tool",
        keywords=tuple(_tokenize(normalized)),
        args=tuple(),
        deferred=True,
    )


def tool_index(tool_names: list[str]) -> list[ToolCatalogEntry]:
    return [describe_tool(name) for name in normalize_requested_tools(tool_names)]


def _tool_match_score(entry: ToolCatalogEntry, query: str) -> int:
    tokens = _tokenize(query)
    if not tokens:
        return 0
    score = 0
    name_tokens = _tokenize(entry.name)
    if tokens & name_tokens:
        score += 5
    for keyword in entry.keywords:
        keyword_tokens = _tokenize(keyword)
        if not keyword_tokens:
            continue
        if keyword_tokens <= tokens:
            score += 3
        elif tokens & keyword_tokens:
            score += 1
    return score


def search_tools(query: str, tool_names: list[str], *, limit: int = 8) -> list[str]:
    entries = tool_index(tool_names)
    scored: list[tuple[int, str]] = []
    for entry in entries:
        score = _tool_match_score(entry, query)
        if score <= 0:
            continue
        scored.append((score, entry.name))
    scored.sort(key=lambda item: (-item[0], item[1]))

    ranked: list[str] = []
    for _score, name in scored:
        if name in ranked:
            continue
        ranked.append(name)
        if len(ranked) >= max(1, limit):
            break
    return ranked


def select_tools_for_turn(
    tool_names: list[str],
    query: str,
    *,
    max_tools: int = 10,
    min_tools: int = 4,
) -> ToolSelection:
    requested = normalize_requested_tools(tool_names)
    if len(requested) <= max_tools:
        return ToolSelection(selected=requested, dropped=[], matched=requested)

    entries = {entry.name: entry for entry in tool_index(requested)}
    selected: list[str] = []

    # Always keep non-deferred tools so core workflows remain available.
    for name in requested:
        entry = entries[name]
        if entry.deferred:
            continue
        selected.append(name)
        if len(selected) >= max_tools:
            break

    ranked = search_tools(query, requested, limit=max_tools)
    for name in ranked:
        if name in selected:
            continue
        selected.append(name)
        if len(selected) >= max_tools:
            break

    if len(selected) < min_tools:
        for name in requested:
            if name in selected:
                continue
            selected.append(name)
            if len(selected) >= min_tools or len(selected) >= max_tools:
                break

    dropped = [name for name in requested if name not in selected]
    return ToolSelection(selected=selected, dropped=dropped, matched=ranked)
