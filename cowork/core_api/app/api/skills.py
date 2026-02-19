from __future__ import annotations

import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import Skill, UserSkillState
from app.skills_catalog import DEFAULT_SKILL_CATALOG, SkillCatalogEntry

router = APIRouter(tags=["skills"])

_SKILL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_SKILL_ZIP_MAX_BYTES = 8 * 1024 * 1024
_ALLOWED_CUSTOM_SOURCES = {"custom"}


class SkillToggleRequest(BaseModel):
    enabled: bool


class SkillOut(BaseModel):
    skill_id: str
    name: str
    description: str
    source: str
    domains: list[str]
    trigger_keywords: list[str]
    trigger_extensions: list[str]
    enabled_by_default: bool
    enabled: bool
    user_owned: bool
    storage_path: str | None = None
    created_at: datetime
    updated_at: datetime


def _normalize_skill_id(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]", "_", normalized)
    normalized = re.sub(r"[_-]{2,}", "_", normalized).strip("_-")
    return normalized


def _build_skill_out(skill: Skill, enabled: bool, user_id: int) -> SkillOut:
    return SkillOut(
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.description,
        source=skill.source,
        domains=list(skill.domains or []),
        trigger_keywords=list(skill.trigger_keywords or []),
        trigger_extensions=list(skill.trigger_extensions or []),
        enabled_by_default=skill.enabled_by_default,
        enabled=enabled,
        user_owned=bool(skill.owner_user_id == user_id),
        storage_path=skill.storage_path,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _ensure_default_catalog(session: Session) -> None:
    existing = session.exec(select(Skill)).all()
    by_skill_id = {entry.skill_id: entry for entry in existing}
    now = datetime.utcnow()
    changed = False
    for catalog_entry in DEFAULT_SKILL_CATALOG:
        record = by_skill_id.get(catalog_entry.skill_id)
        if record is None:
            session.add(
                Skill(
                    skill_id=catalog_entry.skill_id,
                    name=catalog_entry.name,
                    description=catalog_entry.description,
                    source=catalog_entry.source,
                    domains=list(catalog_entry.domains),
                    trigger_keywords=list(catalog_entry.trigger_keywords),
                    trigger_extensions=list(catalog_entry.trigger_extensions),
                    enabled_by_default=catalog_entry.enabled_by_default,
                    created_at=now,
                    updated_at=now,
                )
            )
            changed = True
            continue
        if record.source == "custom":
            continue
        if _catalog_changed(record, catalog_entry):
            record.name = catalog_entry.name
            record.description = catalog_entry.description
            record.source = catalog_entry.source
            record.domains = list(catalog_entry.domains)
            record.trigger_keywords = list(catalog_entry.trigger_keywords)
            record.trigger_extensions = list(catalog_entry.trigger_extensions)
            record.enabled_by_default = catalog_entry.enabled_by_default
            record.updated_at = now
            session.add(record)
            changed = True
    if changed:
        session.commit()


def _catalog_changed(record: Skill, catalog_entry: SkillCatalogEntry) -> bool:
    return (
        record.name != catalog_entry.name
        or record.description != catalog_entry.description
        or record.source != catalog_entry.source
        or list(record.domains or []) != list(catalog_entry.domains)
        or list(record.trigger_keywords or []) != list(catalog_entry.trigger_keywords)
        or list(record.trigger_extensions or []) != list(catalog_entry.trigger_extensions)
        or record.enabled_by_default != catalog_entry.enabled_by_default
    )


def _parse_skill_toml_from_zip(zip_path: Path) -> dict[str, str]:
    with zipfile.ZipFile(zip_path) as archive:
        skill_toml_members = [
            name for name in archive.namelist() if name.endswith("skill.toml") and not name.startswith("__MACOSX/")
        ]
        if not skill_toml_members:
            raise HTTPException(status_code=400, detail="Zip must include skill.toml")
        if len(skill_toml_members) > 1:
            raise HTTPException(status_code=400, detail="Zip must include exactly one skill.toml")
        content = archive.read(skill_toml_members[0]).decode("utf-8")
    parsed: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if key in {"id", "name", "description", "version"}:
            parsed[key] = value
    required = ("id", "name", "version")
    missing = [key for key in required if not parsed.get(key)]
    if missing:
        raise HTTPException(status_code=400, detail=f"skill.toml missing required keys: {', '.join(missing)}")
    parsed["description"] = parsed.get("description", "")
    return parsed


def _custom_skill_base_dir() -> Path:
    base = Path.home() / ".cowork" / "skills" / "custom"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        member_name = member.filename
        if member_name.startswith("/") or ".." in Path(member_name).parts:
            raise HTTPException(status_code=400, detail="Zip contains unsafe file paths")
        target_path = (destination / member_name).resolve()
        if destination not in target_path.parents and target_path != destination:
            raise HTTPException(status_code=400, detail="Zip contains unsafe file paths")
    archive.extractall(destination)


@router.get("/skills", response_model=list[SkillOut])
def list_skills(
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[SkillOut]:
    _ensure_default_catalog(session)
    skills = session.exec(
        select(Skill).where((Skill.owner_user_id.is_(None)) | (Skill.owner_user_id == user.id))
    ).all()
    user_state_rows = session.exec(
        select(UserSkillState).where(UserSkillState.user_id == user.id)
    ).all()
    state_by_skill_id = {row.skill_id: row.enabled for row in user_state_rows}
    ordered = sorted(skills, key=lambda row: (row.source != "built_in", row.source, row.name.lower()))
    return [
        _build_skill_out(
            skill,
            enabled=state_by_skill_id.get(skill.skill_id, skill.enabled_by_default),
            user_id=user.id,
        )
        for skill in ordered
    ]


@router.put("/skills/{skill_id}/toggle", response_model=SkillOut)
def set_skill_enabled(
    skill_id: str,
    request: SkillToggleRequest,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SkillOut:
    _ensure_default_catalog(session)
    normalized_skill_id = _normalize_skill_id(skill_id)
    skill = session.exec(
        select(Skill).where(
            Skill.skill_id == normalized_skill_id,
            ((Skill.owner_user_id.is_(None)) | (Skill.owner_user_id == user.id)),
        )
    ).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    state = session.exec(
        select(UserSkillState).where(
            UserSkillState.user_id == user.id,
            UserSkillState.skill_id == normalized_skill_id,
        )
    ).first()
    now = datetime.utcnow()
    if state:
        state.enabled = request.enabled
        state.updated_at = now
        session.add(state)
    else:
        session.add(
            UserSkillState(
                user_id=user.id,
                skill_id=normalized_skill_id,
                enabled=request.enabled,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
    return _build_skill_out(skill, enabled=request.enabled, user_id=user.id)


@router.post("/skills/upload", response_model=SkillOut)
async def upload_skill_zip(
    file: UploadFile = File(...),
    enabled: bool = Form(default=True),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SkillOut:
    _ensure_default_catalog(session)
    filename = file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported")
    content = await file.read()
    if len(content) > _SKILL_ZIP_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Skill zip exceeds 8MB limit")

    with tempfile.TemporaryDirectory(prefix="skill-upload-") as tmpdir:
        temp_zip = Path(tmpdir) / "skill.zip"
        temp_zip.write_bytes(content)
        try:
            parsed = _parse_skill_toml_from_zip(temp_zip)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Invalid zip archive") from exc

    normalized_skill_id = _normalize_skill_id(parsed["id"])
    if not _SKILL_ID_PATTERN.fullmatch(normalized_skill_id):
        raise HTTPException(status_code=400, detail="Invalid skill id format in skill.toml")

    existing = session.exec(
        select(Skill).where(Skill.skill_id == normalized_skill_id)
    ).first()
    if existing and existing.owner_user_id not in {None, user.id}:
        raise HTTPException(status_code=409, detail="Skill id already exists")
    if existing and existing.source not in _ALLOWED_CUSTOM_SOURCES:
        raise HTTPException(status_code=409, detail="Cannot overwrite built-in or example skill id")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    skill_storage_dir = _custom_skill_base_dir() / str(user.id) / f"{normalized_skill_id}_{timestamp}"
    skill_storage_dir.mkdir(parents=True, exist_ok=True)
    skill_zip_path = skill_storage_dir / "skill.zip"
    skill_zip_path.write_bytes(content)
    with zipfile.ZipFile(skill_zip_path) as archive:
        _safe_extract_zip(archive, skill_storage_dir / "contents")

    now = datetime.utcnow()
    if existing:
        existing.name = parsed["name"]
        existing.description = parsed.get("description", "")
        existing.source = "custom"
        existing.domains = []
        existing.trigger_keywords = []
        existing.trigger_extensions = []
        existing.owner_user_id = user.id
        existing.storage_path = str(skill_storage_dir)
        existing.enabled_by_default = bool(enabled)
        existing.updated_at = now
        session.add(existing)
        skill_record = existing
    else:
        skill_record = Skill(
            skill_id=normalized_skill_id,
            name=parsed["name"],
            description=parsed.get("description", ""),
            source="custom",
            domains=[],
            trigger_keywords=[],
            trigger_extensions=[],
            owner_user_id=user.id,
            storage_path=str(skill_storage_dir),
            enabled_by_default=bool(enabled),
            created_at=now,
            updated_at=now,
        )
        session.add(skill_record)
    session.commit()
    session.refresh(skill_record)

    state = session.exec(
        select(UserSkillState).where(
            UserSkillState.user_id == user.id,
            UserSkillState.skill_id == normalized_skill_id,
        )
    ).first()
    if state:
        state.enabled = bool(enabled)
        state.updated_at = now
        session.add(state)
    else:
        session.add(
            UserSkillState(
                user_id=user.id,
                skill_id=normalized_skill_id,
                enabled=bool(enabled),
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
    session.refresh(skill_record)

    return _build_skill_out(skill_record, enabled=bool(enabled), user_id=user.id)
