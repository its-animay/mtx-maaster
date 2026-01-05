import threading
import time
from typing import Dict, List

from fastapi import Depends, HTTPException, status

from app.security.api_keys import verify_api_key


class RateLimiter:
    """In-memory sliding window rate limiter keyed by hashed API key."""

    def __init__(self, limit: int = 60, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self._lock = threading.Lock()
        self._requests: Dict[str, List[float]] = {}

    def __call__(self, hashed_api_key: str = Depends(verify_api_key)) -> None:
        now = time.time()
        window_start = now - self.window
        with self._lock:
            timestamps = self._requests.get(hashed_api_key, [])
            timestamps = [ts for ts in timestamps if ts >= window_start]
            if len(timestamps) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded ({self.limit} requests/{self.window}s)",
                )
            timestamps.append(now)
            self._requests[hashed_api_key] = timestamps
