from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import os
from pathlib import Path
import re
import sys
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse

from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import engine
from app.models import Artifact, ChatHistory

BLOCKED_ARTIFACT_SEGMENTS = {
    ".initial_env",
    ".venv",
    "venv",
    "site-packages",
    "dist-info",
    "__pycache__",
    ".git",
    "node_modules",
}
BLOCKED_ARTIFACT_METADATA_NAMES = {
    "top_level.txt",
    "entry_points.txt",
    "dependency_links.txt",
    "sources.txt",
    "api_tests.txt",
}


def resolve_workdir_base() -> Path:
    base_dir = os.environ.get("COWORK_WORKDIR")
    if base_dir:
        return Path(base_dir).expanduser().resolve()
    return (Path.home() / ".cowork" / "workdir").resolve()


def normalize_name_for_denylist(value: str) -> str:
    normalized = re.sub(r"[\s-]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized)


def normalize_family_segment(value: str) -> str:
    normalized = re.sub(r"[\s_-]+", "", value.strip().lower())
    return re.sub(r"[^a-z0-9.]", "", normalized)


def metadata_name_blocked(name: str) -> bool:
    if not name:
        return False
    return normalize_name_for_denylist(name) in BLOCKED_ARTIFACT_METADATA_NAMES


def decode_candidate(value: str) -> str:
    text = value.strip()
    if text.lower().startswith("file://"):
        text = text[7:]
    return unquote(text)


def split_path_segments(path_text: str) -> list[str]:
    normalized = decode_candidate(path_text)
    normalized = normalized.split("?", 1)[0].split("#", 1)[0].replace("\\", "/")
    return [segment.strip().lower() for segment in normalized.split("/") if segment.strip()]


def has_blocked_segment(path_text: str) -> bool:
    for segment in split_path_segments(path_text):
        if segment in BLOCKED_ARTIFACT_SEGMENTS:
            return True
        if segment.endswith(".dist-info"):
            return True
        if "site-packages" in segment:
            return True
    return False


def basename_from_path(path_text: str) -> str:
    normalized = decode_candidate(path_text).split("?", 1)[0].split("#", 1)[0].replace("\\", "/")
    return normalized.split("/")[-1].strip()


def extract_generated_target(content_url: str | None) -> tuple[str, str] | None:
    if not content_url:
        return None
    parsed = urlparse(content_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 4:
        return None
    if path_parts[0] != "files" or path_parts[1] != "generated":
        return None
    if path_parts[3] != "download":
        return None

    project_id = path_parts[2]
    rel_values = parse_qs(parsed.query).get("path", [])
    if not rel_values:
        return None
    relative_path = decode_candidate(rel_values[0]).replace("\\", "/").lstrip("/")
    return project_id, relative_path


def path_candidates_from_artifact(artifact: Artifact) -> list[str]:
    candidates: list[str] = []

    if artifact.content_url:
        value = artifact.content_url.strip()
        if value:
            candidates.append(value)
            parsed = urlparse(value)
            path_values = parse_qs(parsed.query).get("path", [])
            candidates.extend(path_values)

    if artifact.name:
        candidates.append(artifact.name)

    return candidates


def is_polluted_artifact(artifact: Artifact) -> bool:
    if metadata_name_blocked(artifact.name):
        return True

    for candidate in path_candidates_from_artifact(artifact):
        if has_blocked_segment(candidate):
            return True
        if metadata_name_blocked(basename_from_path(candidate)):
            return True
    return False


def is_stale_generated_artifact(artifact: Artifact, workdir_base: Path) -> bool:
    target = extract_generated_target(artifact.content_url)
    if not target:
        return False

    project_id, relative_path = target
    project_dir = (workdir_base / project_id).resolve()
    file_path = (project_dir / relative_path).resolve()

    if project_dir not in file_path.parents and file_path != project_dir:
        return True
    return not (file_path.exists() and file_path.is_file())


def canonical_variant_key(artifact: Artifact) -> str:
    target = extract_generated_target(artifact.content_url)
    raw_path = target[1] if target else (artifact.name or "")
    normalized = decode_candidate(raw_path).split("?", 1)[0].split("#", 1)[0].replace("\\", "/")
    segments = [normalize_family_segment(segment) for segment in normalized.split("/") if segment.strip()]
    if not segments:
        return normalize_family_segment(artifact.name or "")
    return "/".join(segments)


def row_rank(artifact: Artifact, workdir_base: Path) -> tuple[int, float, int]:
    exists_flag = 0
    target = extract_generated_target(artifact.content_url)
    if target:
        project_id, relative_path = target
        project_dir = (workdir_base / project_id).resolve()
        file_path = (project_dir / relative_path).resolve()
        if (project_dir in file_path.parents or file_path == project_dir) and file_path.exists() and file_path.is_file():
            exists_flag = 1
    created = artifact.created_at
    created_ts = created.timestamp() if isinstance(created, datetime) else 0.0
    artifact_id = int(artifact.id or 0)
    return exists_flag, created_ts, artifact_id


def collect_task_ids(
    session: Session,
    project_ids: Iterable[str],
    task_ids: Iterable[str],
) -> set[str]:
    selected: set[str] = {task_id for task_id in task_ids if task_id}
    project_ids = [project_id for project_id in project_ids if project_id]
    if not project_ids:
        return selected

    statement = select(ChatHistory.task_id).where(ChatHistory.project_id.in_(project_ids))
    for task_id in session.exec(statement):
        if task_id:
            selected.add(task_id)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup polluted artifact rows from core_api database.")
    parser.add_argument("--project-id", action="append", default=[], help="Project ID to clean (repeatable).")
    parser.add_argument("--task-id", action="append", default=[], help="Task ID to clean (repeatable).")
    parser.add_argument("--all", action="store_true", help="Sweep all artifact rows across all users/projects.")
    parser.add_argument("--apply", action="store_true", help="Apply deletion. Without this flag, runs in dry-run mode.")
    args = parser.parse_args()

    if not args.all and not args.project_id and not args.task_id:
        parser.error("Provide --project-id or --task-id, or use --all for a full sweep.")

    workdir_base = resolve_workdir_base()

    with Session(engine) as session:
        selected_task_ids = collect_task_ids(session, args.project_id, args.task_id)

        statement = select(Artifact).order_by(Artifact.id.asc())
        if not args.all:
            if not selected_task_ids:
                print("No matching task_ids found for provided filters.")
                return 0
            statement = statement.where(Artifact.task_id.in_(selected_task_ids))

        rows = list(session.exec(statement).all())

        reasons_by_id: dict[int, str] = {}
        remaining: list[Artifact] = []

        for row in rows:
            row_id = int(row.id or 0)
            if is_polluted_artifact(row):
                reasons_by_id[row_id] = "denylist"
                continue
            if is_stale_generated_artifact(row, workdir_base):
                reasons_by_id[row_id] = "stale_generated"
                continue
            remaining.append(row)

        groups: dict[tuple[str, str], list[Artifact]] = defaultdict(list)
        for row in remaining:
            groups[(row.task_id, canonical_variant_key(row))].append(row)

        for group_rows in groups.values():
            if len(group_rows) <= 1:
                continue
            keep = max(group_rows, key=lambda row: row_rank(row, workdir_base))
            for row in group_rows:
                row_id = int(row.id or 0)
                keep_id = int(keep.id or 0)
                if row_id == keep_id:
                    continue
                reasons_by_id[row_id] = "duplicate_canonical"

        delete_rows = [row for row in rows if int(row.id or 0) in reasons_by_id]

        print(f"Artifacts scanned: {len(rows)}")
        print(f"Artifacts matched for deletion: {len(delete_rows)}")

        if delete_rows:
            reason_counts = Counter(reasons_by_id[int(row.id or 0)] for row in delete_rows)
            print("Deletion reasons:")
            for reason, count in reason_counts.most_common():
                print(f"  - {reason}: {count}")

            by_task = Counter(row.task_id for row in delete_rows)
            print("Top affected task_ids:")
            for task_id, count in by_task.most_common(10):
                print(f"  - {task_id}: {count}")

            print("Sample rows:")
            for row in delete_rows[:12]:
                reason = reasons_by_id[int(row.id or 0)]
                print(
                    f"  - id={row.id} reason={reason} task_id={row.task_id} "
                    f"name={row.name!r} content_url={row.content_url!r}"
                )

        if not args.apply:
            print("Dry run complete. Re-run with --apply to delete matched rows.")
            return 0

        for row in delete_rows:
            session.delete(row)
        session.commit()
        print(f"Deleted {len(delete_rows)} artifact rows.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
