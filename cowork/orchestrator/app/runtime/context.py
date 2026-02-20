from __future__ import annotations

import os
import re
from pathlib import Path

from app.clients.core_api import fetch_configs


def _parse_summary(summary_text: str) -> tuple[str | None, str | None]:
    if not summary_text:
        return None, None
    if "|" in summary_text:
        name, summary = summary_text.split("|", 1)
        name = name.strip() or None
        summary = summary.strip() or None
        return name, summary
    return None, summary_text.strip()


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
