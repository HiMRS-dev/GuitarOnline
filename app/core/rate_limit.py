"""In-memory sliding-window rate limiter."""

from __future__ import annotations

import asyncio
import math
from collections import defaultdict, deque
from collections.abc import Callable


class InMemorySlidingWindowRateLimiter:
    """Rate limiter using sliding window over event timestamps."""

    def __init__(self, now_provider: Callable[[], float] | None = None) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._now = now_provider

    def _current_time(self) -> float:
        if self._now is not None:
            return self._now()
        return asyncio.get_running_loop().time()

    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Try to reserve one request in the time window."""
        now = self._current_time()
        window_start = now - window_seconds

        async with self._lock:
            events = self._events[key]
            while events and events[0] <= window_start:
                events.popleft()

            if len(events) >= max_requests:
                retry_after = max(1, math.ceil((events[0] + window_seconds) - now))
                return False, retry_after

            events.append(now)
            return True, 0

    async def clear(self) -> None:
        """Drop all tracked counters (for tests)."""
        async with self._lock:
            self._events.clear()


_rate_limiter = InMemorySlidingWindowRateLimiter()


def get_rate_limiter() -> InMemorySlidingWindowRateLimiter:
    """Return shared process-local limiter instance."""
    return _rate_limiter
