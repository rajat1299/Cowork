from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.runtime.deps import deps_enabled, get_status, start_install, stream_logs, tail_logs

router = APIRouter(prefix="/ops/deps", tags=["ops"])


@router.get("/status")
def deps_status(
    include_logs: bool = Query(default=False),
    log_tail: int = Query(default=200, ge=0, le=2000),
):
    return get_status(include_logs=include_logs, log_tail=log_tail)


@router.post("/install")
def deps_install(force: bool = Query(default=False)):
    if not deps_enabled():
        raise HTTPException(status_code=403, detail="Dependency installer is disabled")
    return start_install(force=force)


@router.get("/logs")
def deps_logs(limit: int = Query(default=200, ge=0, le=2000)):
    return {"lines": tail_logs(limit)}


@router.get("/stream")
def deps_stream():
    return StreamingResponse(stream_logs(), media_type="text/event-stream")
