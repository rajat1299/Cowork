from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.runtime.context import _resolve_workdir
from app.runtime.sync import fire_and_forget_artifact
from app.runtime.tool_context import current_project_id
from shared.schemas import ArtifactEvent


_FILE_ARTIFACT_PATTERNS = (
    re.compile(
        r"(?:content\s+successfully\s+)?(?:written|saved|created)\s+to\s+file\s*:\s*(?P<path>[^\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:output|artifact|file)\s*:\s*(?P<path>[^\n]+?\.[a-z0-9]{1,8})",
        re.IGNORECASE,
    ),
)
_ABSOLUTE_FILE_PATTERN = re.compile(r"(/[^\s'\"`]+\.[a-z0-9]{1,8})", re.IGNORECASE)
_ARTIFACT_TYPE_BY_EXTENSION = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
}
_ARTIFACT_DEDUPE: dict[str, set[str]] = {}
_ARTIFACT_DEDUPE_LOCK = threading.Lock()


def _collect_tool_artifacts(task_id: str, data: dict) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    payloads.extend(_extract_file_artifacts(task_id, data))
    return payloads


def _artifact_type_from_suffix(path: Path) -> str:
    return _ARTIFACT_TYPE_BY_EXTENSION.get(path.suffix.lower(), "file")


def _resolve_runtime_base_path(task_id: str) -> Path:
    workdir = os.environ.get("CAMEL_WORKDIR")
    if workdir:
        return Path(workdir)
    project_id = current_project_id.get(None) or task_id
    return _resolve_workdir(project_id)


def _build_generated_file_url(base_path: Path, file_path: Path) -> str | None:
    project_id = (
        current_project_id.get(None)
        or _infer_project_id_from_workdir(base_path)
        or _infer_project_id_from_workdir(file_path)
    )
    if not project_id:
        return None
    try:
        relative_path = file_path.relative_to(base_path)
    except ValueError:
        return None
    return f"/files/generated/{project_id}/download?path={quote(str(relative_path))}"


def _infer_project_id_from_workdir(path: Path) -> str | None:
    try:
        resolved = path.resolve()
    except Exception:
        return None
    parts = resolved.parts
    for index, value in enumerate(parts[:-1]):
        if value == "workdir" and index + 1 < len(parts):
            candidate = parts[index + 1]
            if candidate:
                return candidate
    return None


def _mark_artifact_emitted(task_id: str, key: str) -> bool:
    with _ARTIFACT_DEDUPE_LOCK:
        emitted = _ARTIFACT_DEDUPE.setdefault(task_id, set())
        if key in emitted:
            return False
        emitted.add(key)
        return True


def _cleanup_artifact_cache(task_id: str) -> None:
    with _ARTIFACT_DEDUPE_LOCK:
        _ARTIFACT_DEDUPE.pop(task_id, None)


def _normalize_result_path(raw_path: str, base_path: Path) -> Path | None:
    value = raw_path.strip().strip("`'\"")
    value = value.rstrip(".,;")
    if not value:
        return None
    try:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = (base_path / candidate).resolve()
        else:
            candidate = candidate.resolve()
    except Exception:
        return None
    return candidate


def _candidate_paths_from_message(message: str) -> list[str]:
    candidates: list[str] = []
    for pattern in _FILE_ARTIFACT_PATTERNS:
        for match in pattern.finditer(message):
            path_value = match.groupdict().get("path")
            if path_value:
                candidates.append(path_value.strip())
    if not candidates:
        for match in _ABSOLUTE_FILE_PATTERN.finditer(message):
            candidates.append(match.group(1))
    return candidates


def _extract_file_artifacts(task_id: str, data: dict) -> list[dict[str, Any]]:
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return []

    base_path = _resolve_runtime_base_path(task_id)
    now = time.time()
    artifact_payloads: list[dict[str, Any]] = []

    for raw_path in _candidate_paths_from_message(message):
        resolved = _normalize_result_path(raw_path, base_path)
        if resolved is None or not resolved.exists() or not resolved.is_file():
            continue

        path_key = str(resolved)
        if not _mark_artifact_emitted(task_id, path_key):
            continue

        content_url = _build_generated_file_url(base_path, resolved)
        artifact_type = _artifact_type_from_suffix(resolved)
        fire_and_forget_artifact(
            ArtifactEvent(
                task_id=task_id,
                artifact_type=artifact_type,
                name=resolved.name,
                content_url=content_url or str(resolved),
                created_at=now,
            )
        )
        artifact_payloads.append(
            {
                "id": f"artifact-file-{abs(hash((task_id, path_key, int(now * 1000))))}",
                "type": artifact_type,
                "name": resolved.name,
                "content_url": content_url or str(resolved),
                "path": str(resolved),
            }
        )

    return artifact_payloads
