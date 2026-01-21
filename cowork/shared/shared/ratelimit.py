from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable

from fastapi import HTTPException, Request


@dataclass
class SlidingWindowLimiter:
    max_requests: int
    window_seconds: int
    lock: Lock = field(default_factory=Lock)
    requests: dict[str, deque[float]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            bucket = self.requests.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True


def rate_limit(limiter: SlidingWindowLimiter, key_func: Callable[[Request], str]):
    async def dependency(request: Request) -> None:
        key = key_func(request)
        if not limiter.allow(key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return dependency


def ip_key(bucket: str) -> Callable[[Request], str]:
    def _key(request: Request) -> str:
        client = request.client.host if request.client else "unknown"
        return f"{client}:{bucket}"

    return _key
