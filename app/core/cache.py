"""Cache abstractions prepared for future Redis integration."""

from __future__ import annotations

from typing import Protocol


class CacheBackend(Protocol):
    """Protocol for cache providers (Redis, memory, etc.)."""

    async def get(self, key: str) -> str | None:
        """Get cached value by key."""

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set cached value with optional TTL."""

    async def delete(self, key: str) -> None:
        """Delete cached value by key."""


class NoopCacheBackend:
    """Default cache backend used until Redis is connected."""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None
