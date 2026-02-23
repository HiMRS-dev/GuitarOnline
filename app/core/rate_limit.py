"""Rate limiter backends (in-memory and Redis)."""

from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any, Protocol
from uuid import uuid4

from app.core.config import Settings, get_settings


class RateLimiter(Protocol):
    """Common contract for limiter backends."""

    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Try to reserve one request in the time window."""

    async def clear(self) -> None:
        """Drop tracked counters (used in tests)."""


_REDIS_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local window_start = now - window

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)
if count >= limit then
  local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local first_score = now
  if first[2] ~= nil then
    first_score = tonumber(first[2])
  end
  return {0, first_score}
end

redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window))
return {1, 0}
"""


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


class RedisSlidingWindowRateLimiter:
    """Redis-backed sliding-window limiter shared across app instances."""

    def __init__(
        self,
        *,
        redis_url: str,
        namespace: str,
        now_provider: Callable[[], float] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._namespace = namespace
        self._now = now_provider
        self._init_lock = asyncio.Lock()
        self._client: Any | None = None
        self._acquire_script: Any | None = None

    def _current_time(self) -> float:
        if self._now is not None:
            return self._now()
        return time.time()

    def _build_storage_key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    async def _ensure_initialized(self) -> None:
        if self._client is not None and self._acquire_script is not None:
            return

        async with self._init_lock:
            if self._client is None:
                from redis.asyncio import from_url

                self._client = from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )

            if self._acquire_script is None:
                self._acquire_script = self._client.register_script(_REDIS_ACQUIRE_SCRIPT)

    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        await self._ensure_initialized()
        now = self._current_time()
        result = await self._acquire_script(
            keys=[self._build_storage_key(key)],
            args=[now, window_seconds, max_requests, f"{now}:{uuid4().hex}"],
        )

        allowed = bool(int(result[0]))
        if allowed:
            return True, 0

        first_event_time = float(result[1])
        retry_after = max(1, math.ceil((first_event_time + window_seconds) - now))
        return False, retry_after

    async def clear(self) -> None:
        """Delete limiter keys for this namespace."""
        await self._ensure_initialized()
        pattern = f"{self._namespace}:*"
        cursor: int = 0
        while True:
            cursor, keys = await self._client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await self._client.delete(*keys)
            if int(cursor) == 0:
                break


_rate_limiter: RateLimiter | None = None
_rate_limiter_signature: tuple[str, str | None, str] | None = None


def _build_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.auth_rate_limit_backend == "redis":
        return RedisSlidingWindowRateLimiter(
            redis_url=settings.redis_url or "",
            namespace=settings.auth_rate_limit_redis_namespace,
        )
    return InMemorySlidingWindowRateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Return shared limiter instance for configured backend."""
    global _rate_limiter, _rate_limiter_signature
    settings = get_settings()
    signature = (
        settings.auth_rate_limit_backend,
        settings.redis_url,
        settings.auth_rate_limit_redis_namespace,
    )
    if _rate_limiter is None or _rate_limiter_signature != signature:
        _rate_limiter = _build_rate_limiter(settings)
        _rate_limiter_signature = signature
    return _rate_limiter
