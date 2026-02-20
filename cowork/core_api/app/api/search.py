from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import settings
from app.db import get_session
from app.models import SearchUsage
from shared.ratelimit import SlidingWindowLimiter, ip_key, rate_limit

router = APIRouter(prefix="/search", tags=["search"])
_search_limiter = SlidingWindowLimiter(
    max_requests=settings.rate_limit_proxy_per_minute,
    window_seconds=60,
)
_search_rate_limit = rate_limit(_search_limiter, ip_key("search"))

_PROVIDER_EXA = "exa"
_MAX_RESULTS = 3
_USER_DAILY_CAP = 5
_GLOBAL_DAILY_CAP_USD = 2.0
_COST_PER_1K_RESULTS_USD = 5.0


class ExaSearch(BaseModel):
    query: str
    search_type: Literal["auto", "neural", "keyword"] = "auto"
    category: (
        Literal[
            "company",
            "research paper",
            "news",
            "pdf",
            "github",
            "tweet",
            "personal site",
            "linkedin profile",
            "financial report",
        ]
        | None
    ) = None
    num_results: int = _MAX_RESULTS
    include_text: list[str] | None = None
    exclude_text: list[str] | None = None
    use_autoprompt: bool | None = True


def _utc_today():
    return datetime.now(timezone.utc).date()


def _estimate_cost(num_results: int) -> float:
    return (num_results / 1000.0) * _COST_PER_1K_RESULTS_USD


def _validate_exa_request(search: ExaSearch) -> None:
    if not search.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    if not 1 <= search.num_results <= _MAX_RESULTS:
        raise HTTPException(status_code=400, detail=f"num_results must be between 1 and {_MAX_RESULTS}")
    if search.include_text:
        if len(search.include_text) > 1:
            raise HTTPException(status_code=400, detail="include_text can only contain 1 string")
        if len(search.include_text[0].split()) > 5:
            raise HTTPException(status_code=400, detail="include_text string cannot be longer than 5 words")
    if search.exclude_text:
        if len(search.exclude_text) > 1:
            raise HTTPException(status_code=400, detail="exclude_text can only contain 1 string")
        if len(search.exclude_text[0].split()) > 5:
            raise HTTPException(status_code=400, detail="exclude_text string cannot be longer than 5 words")


def _require_server_exa_key() -> str:
    api_key = settings.exa_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="Exa server key is not configured")
    return api_key


def _reserve_usage(
    session: Session,
    user_id: int,
    num_results: int,
    estimated_cost: float,
) -> None:
    today = _utc_today()
    now = datetime.now(timezone.utc)
    with session.begin():
        statement = (
            select(SearchUsage)
            .where(
                SearchUsage.user_id == user_id,
                SearchUsage.provider == _PROVIDER_EXA,
                SearchUsage.date == today,
            )
            .with_for_update()
        )
        usage = session.exec(statement).first()
        if not usage:
            usage = SearchUsage(
                user_id=user_id,
                provider=_PROVIDER_EXA,
                date=today,
                requests_count=0,
                results_count=0,
                cost_usd_estimate=0.0,
                created_at=now,
                updated_at=now,
            )
            session.add(usage)

        if usage.requests_count >= _USER_DAILY_CAP:
            raise HTTPException(status_code=429, detail="Daily search limit reached")

        global_cost = session.exec(
            select(func.coalesce(func.sum(SearchUsage.cost_usd_estimate), 0.0)).where(
                SearchUsage.provider == _PROVIDER_EXA,
                SearchUsage.date == today,
            )
        ).one()
        if global_cost + estimated_cost > _GLOBAL_DAILY_CAP_USD:
            raise HTTPException(status_code=402, detail="Global search budget exhausted")

        usage.requests_count += 1
        usage.results_count += num_results
        usage.cost_usd_estimate += estimated_cost
        usage.updated_at = now
        session.add(usage)


def _rollback_usage(
    session: Session,
    user_id: int,
    num_results: int,
    estimated_cost: float,
) -> None:
    today = _utc_today()
    now = datetime.now(timezone.utc)
    with session.begin():
        statement = (
            select(SearchUsage)
            .where(
                SearchUsage.user_id == user_id,
                SearchUsage.provider == _PROVIDER_EXA,
                SearchUsage.date == today,
            )
            .with_for_update()
        )
        usage = session.exec(statement).first()
        if not usage:
            return
        usage.requests_count = max(0, usage.requests_count - 1)
        usage.results_count = max(0, usage.results_count - num_results)
        usage.cost_usd_estimate = max(0.0, usage.cost_usd_estimate - estimated_cost)
        usage.updated_at = now
        session.add(usage)


@router.post("/exa", dependencies=[Depends(_search_rate_limit)])
def exa_search(
    search: ExaSearch,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _validate_exa_request(search)
    api_key = _require_server_exa_key()
    estimated_cost = _estimate_cost(search.num_results)

    _reserve_usage(session, user.id, search.num_results, estimated_cost)

    payload = {
        "query": search.query,
        "type": search.search_type,
        "category": search.category,
        "num_results": search.num_results,
        "include_text": search.include_text,
        "exclude_text": search.exclude_text,
        "use_autoprompt": search.use_autoprompt,
    }

    try:
        response = httpx.post(
            "https://api.exa.ai/search",
            json=payload,
            headers={"x-api-key": api_key},
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        _rollback_usage(session, user.id, search.num_results, estimated_cost)
        raise HTTPException(status_code=502, detail="Exa API request failed")

    return response.json()
