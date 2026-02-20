from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.runtime.events import StepEvent


_TRACE_LOGGER: logging.Logger | None = None


def _get_trace_logger() -> logging.Logger:
    global _TRACE_LOGGER
    if _TRACE_LOGGER is not None:
        return _TRACE_LOGGER

    log_path = os.environ.get("COWORK_RUNTIME_LOG_PATH")
    if not log_path:
        log_path = os.path.expanduser("~/.cowork/logs/runtime.log")

    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    trace_logger = logging.getLogger("cowork.runtime.trace")
    trace_logger.setLevel(logging.INFO)
    trace_logger.propagate = False
    if not trace_logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        trace_logger.addHandler(handler)
    _TRACE_LOGGER = trace_logger
    return trace_logger


def _trace_log(event: str, payload: dict[str, Any]) -> None:
    logger = _get_trace_logger()
    payload = {**payload, "event": event, "ts": datetime.now(timezone.utc).isoformat() + "Z"}
    logger.info(json.dumps(payload))


def _trace_step(task_id: str, step: StepEvent, data: dict) -> None:
    if step in {StepEvent.streaming, StepEvent.decompose_text}:
        chunk = data.get("chunk") if step == StepEvent.streaming else data.get("content")
        if isinstance(chunk, str):
            preview = chunk[:200]
            _trace_log(
                "step",
                {
                    "task_id": task_id,
                    "step": step.value,
                    "chunk_len": len(chunk),
                    "chunk_preview": preview,
                },
            )
            return
    data_preview = repr(data)
    if len(data_preview) > 2000:
        data_preview = data_preview[:2000] + "...(truncated)"
    _trace_log(
        "step",
        {
            "task_id": task_id,
            "step": step.value,
            "data": data_preview,
        },
    )
