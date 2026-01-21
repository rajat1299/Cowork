from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request


REQUEST_ID_HEADER = "X-Request-Id"


def _resolve_request_id(request: Request) -> str:
    request_id = request.headers.get(REQUEST_ID_HEADER)
    if request_id:
        return request_id
    return uuid.uuid4().hex


def attach_request_logging(app: FastAPI, service_name: str) -> None:
    logger = logging.getLogger(service_name)

    @app.middleware("http")
    async def log_request(request: Request, call_next: Callable):
        request_id = _resolve_request_id(request)
        request.state.request_id = request_id
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        duration_ms = int((time.time() - start) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
            },
        )
        return response
