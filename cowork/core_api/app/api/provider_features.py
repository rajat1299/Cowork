from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.crypto import decrypt_json, encrypt_json
from app.db import get_session
from app.models import Provider, ProviderFeatureFlags

router = APIRouter(tags=["provider-features"])


class ProviderFeatureFlagsCreate(BaseModel):
    provider_id: int
    model: str
    native_web_search_enabled: bool | None = None
    image_generation_enabled: bool | None = None
    audio_enabled: bool | None = None
    tool_use_enabled: bool | None = None
    browser_enabled: bool | None = None
    extra_params_json: dict | None = None


class ProviderFeatureFlagsOut(BaseModel):
    id: int
    user_id: int
    provider_id: int
    model: str
    native_web_search_enabled: bool
    image_generation_enabled: bool
    audio_enabled: bool
    tool_use_enabled: bool
    browser_enabled: bool
    extra_params_json: dict | None
    created_at: datetime
    updated_at: datetime


@router.get("/provider-features", response_model=list[ProviderFeatureFlagsOut])
def list_provider_features(
    provider_id: int | None = Query(default=None),
    model: str | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ProviderFeatureFlagsOut]:
    statement = select(ProviderFeatureFlags).where(ProviderFeatureFlags.user_id == user.id)
    if provider_id is not None:
        statement = statement.where(ProviderFeatureFlags.provider_id == provider_id)
    if model:
        statement = statement.where(ProviderFeatureFlags.model == model)
    records = session.exec(statement).all()
    return [_provider_feature_out(record) for record in records]


@router.put("/provider-features", response_model=ProviderFeatureFlagsOut)
def upsert_provider_features(
    request: ProviderFeatureFlagsCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProviderFeatureFlagsOut:
    provider = session.exec(
        select(Provider).where(Provider.id == request.provider_id, Provider.user_id == user.id)
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    record = session.exec(
        select(ProviderFeatureFlags).where(
            ProviderFeatureFlags.user_id == user.id,
            ProviderFeatureFlags.provider_id == request.provider_id,
            ProviderFeatureFlags.model == request.model,
        )
    ).first()

    if record:
        if request.native_web_search_enabled is not None:
            record.native_web_search_enabled = request.native_web_search_enabled
        if request.image_generation_enabled is not None:
            record.image_generation_enabled = request.image_generation_enabled
        if request.audio_enabled is not None:
            record.audio_enabled = request.audio_enabled
        if request.tool_use_enabled is not None:
            record.tool_use_enabled = request.tool_use_enabled
        if request.browser_enabled is not None:
            record.browser_enabled = request.browser_enabled
        if request.extra_params_json is not None:
            record.extra_params_json = _encrypt_extra_params(request.extra_params_json)
        record.updated_at = datetime.utcnow()
        session.add(record)
        session.commit()
        session.refresh(record)
        return _provider_feature_out(record)

    record = ProviderFeatureFlags(
        user_id=user.id,
        provider_id=request.provider_id,
        model=request.model,
        native_web_search_enabled=bool(request.native_web_search_enabled),
        image_generation_enabled=bool(request.image_generation_enabled),
        audio_enabled=bool(request.audio_enabled),
        tool_use_enabled=bool(request.tool_use_enabled),
        browser_enabled=bool(request.browser_enabled),
        extra_params_json=_encrypt_extra_params(request.extra_params_json)
        if request.extra_params_json is not None
        else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _provider_feature_out(record)


def _encrypt_extra_params(payload: dict) -> dict:
    try:
        return encrypt_json(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _provider_feature_out(record: ProviderFeatureFlags) -> ProviderFeatureFlagsOut:
    try:
        extra_params = decrypt_json(record.extra_params_json)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ProviderFeatureFlagsOut(
        id=record.id,
        user_id=record.user_id,
        provider_id=record.provider_id,
        model=record.model,
        native_web_search_enabled=record.native_web_search_enabled,
        image_generation_enabled=record.image_generation_enabled,
        audio_enabled=record.audio_enabled,
        tool_use_enabled=record.tool_use_enabled,
        browser_enabled=record.browser_enabled,
        extra_params_json=extra_params,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
