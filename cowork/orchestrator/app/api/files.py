from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/files", tags=["files"])


class UploadedFileInfo(BaseModel):
    id: str
    name: str
    content_type: str | None = None
    size: int
    path: str
    relative_path: str
    url: str


class UploadResponse(BaseModel):
    files: list[UploadedFileInfo]


def _sanitize_identifier(value: str, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in (value or ""))
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


async def _save_upload(upload: UploadFile, dest_path: Path) -> int:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with dest_path.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            size += len(chunk)
    await upload.close()
    return size


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    project_id: str = Form(...),
    task_id: str | None = Form(None),
    files: List[UploadFile] = File(...),
) -> UploadResponse:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    workdir = _resolve_workdir(project_id)
    uploads_dir = workdir / "uploads"
    meta_dir = uploads_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    bucket = _sanitize_identifier(task_id or "general", "general")
    bucket_dir = uploads_dir / bucket
    bucket_dir.mkdir(parents=True, exist_ok=True)

    uploaded: list[UploadedFileInfo] = []
    for upload in files:
        file_id = uuid4().hex
        original_name = upload.filename or "upload"
        safe_name = _sanitize_identifier(original_name, "upload")
        stored_name = f"{file_id}_{safe_name}"
        file_path = bucket_dir / stored_name
        size = await _save_upload(upload, file_path)
        relative_path = str(file_path.relative_to(workdir))
        content_type = upload.content_type

        meta = {
            "id": file_id,
            "name": original_name,
            "content_type": content_type,
            "size": size,
            "relative_path": relative_path,
            "created_at": int(time.time()),
        }
        meta_path = meta_dir / f"{file_id}.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        uploaded.append(
            UploadedFileInfo(
                id=file_id,
                name=original_name,
                content_type=content_type,
                size=size,
                path=str(file_path),
                relative_path=relative_path,
                url=f"/files/{project_id}/{file_id}",
            )
        )

    return UploadResponse(files=uploaded)


@router.get("/{project_id}/{file_id}")
def download_file(project_id: str, file_id: str) -> FileResponse:
    workdir = _resolve_workdir(project_id)
    meta_path = workdir / "uploads" / "meta" / f"{file_id}.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="File metadata not found")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=404, detail="File metadata invalid")

    relative_path = meta.get("relative_path")
    if not isinstance(relative_path, str):
        raise HTTPException(status_code=404, detail="File metadata invalid")
    file_path = (workdir / relative_path).resolve()
    if workdir not in file_path.parents and file_path != workdir:
        raise HTTPException(status_code=403, detail="Invalid file path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        file_path,
        filename=meta.get("name") or file_path.name,
        media_type=meta.get("content_type") or "application/octet-stream",
    )


@router.get("/generated/{project_id}/download")
def download_generated_file(project_id: str, path: str = Query(...)) -> FileResponse:
    workdir = _resolve_workdir(project_id)
    requested = Path(path)
    if requested.is_absolute():
        file_path = requested.resolve()
    else:
        file_path = (workdir / requested).resolve()
    if workdir not in file_path.parents and file_path != workdir:
        raise HTTPException(status_code=403, detail="Invalid file path")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
