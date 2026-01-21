from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import settings
from app.config_catalog import group_aliases
from app.db import get_session
from app.models import Config
from shared.ratelimit import SlidingWindowLimiter, ip_key, rate_limit

router = APIRouter(prefix="/proxy", tags=["mcp-proxy"])
_proxy_limiter = SlidingWindowLimiter(
    max_requests=settings.rate_limit_proxy_per_minute,
    window_seconds=60,
)
_proxy_rate_limit = rate_limit(_proxy_limiter, ip_key("proxy"))


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
    num_results: int = 10
    include_text: list[str] | None = None
    exclude_text: list[str] | None = None
    use_autoprompt: bool | None = True
    text: bool | None = False


def _get_group_config(session: Session, user_id: int, group: str) -> dict[str, str]:
    aliases = group_aliases(group)
    if not aliases:
        return {}
    statement = select(Config).where(Config.user_id == user_id, Config.group.in_(aliases))
    records = session.exec(statement).all()
    return {record.name: record.value for record in records}


def _require_config_value(configs: dict[str, str], key: str) -> str:
    value = configs.get(key)
    if not value:
        raise HTTPException(status_code=400, detail=f"Missing config value: {key}")
    return value


def _validate_exa_request(search: ExaSearch) -> None:
    if not search.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    if not 1 <= search.num_results <= 100:
        raise HTTPException(status_code=400, detail="num_results must be between 1 and 100")
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


@router.post("/exa", dependencies=[Depends(_proxy_rate_limit)])
def exa_search(
    search: ExaSearch,
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _validate_exa_request(search)
    configs = _get_group_config(session, user.id, "search")
    api_key = _require_config_value(configs, "EXA_API_KEY")

    payload = {
        "query": search.query,
        "type": search.search_type,
        "category": search.category,
        "num_results": search.num_results,
        "include_text": search.include_text,
        "exclude_text": search.exclude_text,
        "use_autoprompt": search.use_autoprompt,
    }
    url = "https://api.exa.ai/search_and_contents" if search.text else "https://api.exa.ai/search"

    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"x-api-key": api_key},
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Exa API request failed")

    return response.json()


@router.get("/google", dependencies=[Depends(_proxy_rate_limit)])
def google_search(
    query: str = Query(..., min_length=1),
    search_type: Literal["web", "image"] = "web",
    num_results: int = Query(default=10, ge=1, le=10),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    configs = _get_group_config(session, user.id, "search")
    api_key = _require_config_value(configs, "GOOGLE_API_KEY")
    search_engine_id = _require_config_value(configs, "SEARCH_ENGINE_ID")

    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": query,
        "num": num_results,
    }
    if search_type == "image":
        params["searchType"] = "image"

    try:
        response = httpx.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Google search API request failed")

    data = response.json()
    items = data.get("items")
    if not items:
        raise HTTPException(status_code=502, detail="Google search API returned no results")

    responses: list[dict] = []
    for idx, item in enumerate(items, start=1):
        if search_type == "image":
            image_info = item.get("image", {})
            response_item = {
                "result_id": idx,
                "title": item.get("title"),
                "image_url": item.get("link"),
                "display_link": item.get("displayLink"),
                "context_url": image_info.get("contextLink"),
            }
            if image_info.get("width"):
                response_item["width"] = int(image_info.get("width"))
            if image_info.get("height"):
                response_item["height"] = int(image_info.get("height"))
            responses.append(response_item)
        else:
            meta_tags = item.get("pagemap", {}).get("metatags", [])
            long_description = None
            if meta_tags:
                long_description = meta_tags[0].get("og:description")
            responses.append(
                {
                    "result_id": idx,
                    "title": item.get("title"),
                    "description": item.get("snippet"),
                    "long_description": long_description,
                    "url": item.get("link"),
                }
            )
    return responses
