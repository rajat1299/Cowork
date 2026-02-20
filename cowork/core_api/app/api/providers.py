from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.internal_auth import require_internal_key
from app.models import Provider

router = APIRouter(tags=["providers"])


class ProviderCreate(BaseModel):
    provider_name: str
    model_type: str
    api_key: str
    endpoint_url: str = ""
    encrypted_config: dict | None = None
    prefer: bool = False
    is_valid: bool = False


class ProviderOut(BaseModel):
    id: int
    user_id: int
    provider_name: str
    model_type: str
    endpoint_url: str
    encrypted_config: dict | None
    prefer: bool
    is_valid: bool
    created_at: datetime
    updated_at: datetime
    api_key_last4: str | None
    api_key_set: bool


class ProviderUpdate(BaseModel):
    provider_name: str | None = None
    model_type: str | None = None
    api_key: str | None = None
    endpoint_url: str | None = None
    encrypted_config: dict | None = None
    prefer: bool | None = None
    is_valid: bool | None = None


class ProviderPrefer(BaseModel):
    provider_id: int


class ProviderInternalOut(ProviderOut):
    api_key: str


def _set_preferred_provider(session: Session, user_id: int, provider_id: int) -> Provider:
    provider = session.exec(
        select(Provider).where(Provider.id == provider_id, Provider.user_id == user_id)
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    statement = select(Provider).where(Provider.user_id == user_id)
    providers = session.exec(statement).all()
    for record in providers:
        record.prefer = False
        record.updated_at = datetime.now(timezone.utc)
    provider.prefer = True
    provider.updated_at = datetime.now(timezone.utc)
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


def _provider_out(record: Provider) -> ProviderOut:
    api_key_last4 = record.api_key[-4:] if record.api_key else None
    return ProviderOut(
        id=record.id,
        user_id=record.user_id,
        provider_name=record.provider_name,
        model_type=record.model_type,
        endpoint_url=record.endpoint_url,
        encrypted_config=record.encrypted_config,
        prefer=record.prefer,
        is_valid=record.is_valid,
        created_at=record.created_at,
        updated_at=record.updated_at,
        api_key_last4=api_key_last4,
        api_key_set=bool(record.api_key),
    )


def _provider_internal_out(record: Provider) -> ProviderInternalOut:
    base = _provider_out(record)
    return ProviderInternalOut(**base.model_dump(), api_key=record.api_key)


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(
    keyword: str | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ProviderOut]:
    statement = select(Provider).where(Provider.user_id == user.id)
    if keyword:
        statement = statement.where(Provider.provider_name.ilike(f"%{keyword}%"))
    records = session.exec(statement).all()
    return [_provider_out(record) for record in records]


@router.get(
    "/providers/internal",
    response_model=list[ProviderInternalOut],
    dependencies=[Depends(require_internal_key)],
)
def list_providers_internal(
    keyword: str | None = Query(default=None),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ProviderInternalOut]:
    statement = select(Provider).where(Provider.user_id == user.id)
    if keyword:
        statement = statement.where(Provider.provider_name.ilike(f"%{keyword}%"))
    records = session.exec(statement).all()
    return [_provider_internal_out(record) for record in records]


@router.get("/provider", response_model=ProviderOut)
def get_provider(
    id: int = Query(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProviderOut:
    record = session.exec(
        select(Provider).where(Provider.id == id, Provider.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _provider_out(record)


@router.get(
    "/provider/internal/{provider_id}",
    response_model=ProviderInternalOut,
    dependencies=[Depends(require_internal_key)],
)
def get_provider_internal(
    provider_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProviderInternalOut:
    record = session.exec(
        select(Provider).where(Provider.id == provider_id, Provider.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _provider_internal_out(record)


@router.get("/provider/{provider_id}", response_model=ProviderOut)
def get_provider_by_id(
    provider_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProviderOut:
    record = session.exec(
        select(Provider).where(Provider.id == provider_id, Provider.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _provider_out(record)


@router.post("/provider", response_model=ProviderOut)
def create_provider(
    request: ProviderCreate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProviderOut:
    record = Provider(
        user_id=user.id,
        provider_name=request.provider_name,
        model_type=request.model_type,
        api_key=request.api_key,
        endpoint_url=request.endpoint_url,
        encrypted_config=request.encrypted_config,
        prefer=request.prefer,
        is_valid=request.is_valid,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    if request.prefer:
        record = _set_preferred_provider(session, user.id, record.id)
    return _provider_out(record)


@router.put("/provider/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: int,
    request: ProviderUpdate,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProviderOut:
    record = session.exec(
        select(Provider).where(Provider.id == provider_id, Provider.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    session.refresh(record)
    if request.prefer:
        record = _set_preferred_provider(session, user.id, record.id)
    return _provider_out(record)


@router.delete("/provider/{provider_id}")
def delete_provider(
    provider_id: int,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = session.exec(
        select(Provider).where(Provider.id == provider_id, Provider.user_id == user.id)
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    session.delete(record)
    session.commit()
    return Response(status_code=204)


@router.post("/provider/prefer", response_model=ProviderOut)
def set_prefer_provider(
    request: ProviderPrefer,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProviderOut:
    record = _set_preferred_provider(session, user.id, request.provider_id)
    return _provider_out(record)
