from __future__ import annotations

import os
import re
from pathlib import Path

from app.clients.core_api import fetch_configs


def _strip_markdown(text: str) -> str:
    """Remove common markdown syntax from text to ensure plain display."""
    # Strip leading markdown headings (### Title)
    cleaned = re.sub(r"^#{1,6}\s+", "", text.strip())
    # Strip bold/italic markers
    cleaned = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", cleaned)
    cleaned = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", cleaned)
    # Strip inline code backticks
    cleaned = re.sub(r"`(.+?)`", r"\1", cleaned)
    # Strip leading bullets/numbers (- item, * item, 1. item)
    cleaned = re.sub(r"^\s*[-*]\s+", "", cleaned)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned)
    # Strip blockquote markers
    cleaned = re.sub(r"^>\s+", "", cleaned)
    return cleaned.strip()


def _parse_summary(summary_text: str) -> tuple[str | None, str | None]:
    if not summary_text:
        return None, None
    if "|" in summary_text:
        name, summary = summary_text.split("|", 1)
        name = _strip_markdown(name) or None
        summary = _strip_markdown(summary) if summary else None
        # Truncate title to 60 chars
        if name and len(name) > 60:
            name = name[:57] + "..."
        return name, summary
    return None, _strip_markdown(summary_text)


def _sanitize_identifier(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", value or "")
    return cleaned or fallback


def _resolve_workdir(project_id: str) -> Path:
    base_dir = os.environ.get("COWORK_WORKDIR")
    if base_dir:
        base_path = Path(base_dir).expanduser()
    else:
        base_path = Path.home() / ".cowork" / "workdir"
    safe_project = _sanitize_identifier(project_id, "project")
    workdir = (base_path / safe_project).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def _normalize_attachments(
    attachments: list[object] | None,
    workdir: Path,
) -> list[dict[str, object]]:
    if not attachments:
        return []
    safe: list[dict[str, object]] = []
    for attachment in attachments:
        payload: dict[str, object] | None = None
        if isinstance(attachment, dict):
            payload = attachment
        elif hasattr(attachment, "model_dump"):
            payload = attachment.model_dump()  # type: ignore[attr-defined]
        elif hasattr(attachment, "dict"):
            payload = attachment.dict()  # type: ignore[attr-defined]
        if not payload:
            continue
        raw_path = payload.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        try:
            resolved = Path(raw_path).expanduser().resolve()
        except Exception:
            continue
        if workdir not in resolved.parents and resolved != workdir:
            continue
        normalized = dict(payload)
        normalized["path"] = str(resolved)
        safe.append(normalized)
    return safe


def _attachments_context(attachments: list[dict[str, object]]) -> str:
    if not attachments:
        return ""
    lines = ["", "User attached files:"]
    for attachment in attachments:
        name = attachment.get("name") or "attachment"
        path = attachment.get("path") or ""
        content_type = attachment.get("content_type")
        size = attachment.get("size")
        meta_parts = []
        if isinstance(content_type, str) and content_type:
            meta_parts.append(content_type)
        if isinstance(size, int) and size > 0:
            meta_parts.append(f"{size} bytes")
        meta = f" ({', '.join(meta_parts)})" if meta_parts else ""
        lines.append(f"- {name}{meta}: {path}")
    return "\n".join(lines) + "\n"


async def _load_tool_env(auth_token: str | None) -> dict[str, str]:
    configs = await fetch_configs(auth_token)
    env_vars: dict[str, str] = {}
    for item in configs:
        key = item.get("key") or item.get("name")
        value = item.get("value")
        if not key or value is None:
            continue
        env_vars[str(key)] = str(value)
    if "MCP_REMOTE_CONFIG_DIR" not in env_vars and "MCP_REMOTE_CONFIG_DIR" not in os.environ:
        env_vars["MCP_REMOTE_CONFIG_DIR"] = str(Path.home() / ".cowork" / "mcp-auth")
    return env_vars
