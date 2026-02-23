from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import rate_limit as rate_limit_module
from app.core.rate_limit import InMemorySlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_sliding_window_blocks_after_limit_and_recovers() -> None:
    now_point = [100.0]
    limiter = InMemorySlidingWindowRateLimiter(now_provider=lambda: now_point[0])

    first_allowed, first_retry = await limiter.acquire("k", max_requests=2, window_seconds=10)
    second_allowed, second_retry = await limiter.acquire("k", max_requests=2, window_seconds=10)
    third_allowed, third_retry = await limiter.acquire("k", max_requests=2, window_seconds=10)

    assert first_allowed is True
    assert first_retry == 0
    assert second_allowed is True
    assert second_retry == 0
    assert third_allowed is False
    assert third_retry == 10

    now_point[0] = 110.01
    fourth_allowed, fourth_retry = await limiter.acquire("k", max_requests=2, window_seconds=10)
    assert fourth_allowed is True
    assert fourth_retry == 0


@pytest.mark.asyncio
async def test_clear_drops_all_counters() -> None:
    limiter = InMemorySlidingWindowRateLimiter(now_provider=lambda: 200.0)

    await limiter.acquire("login:1.1.1.1", max_requests=1, window_seconds=60)
    blocked, _ = await limiter.acquire("login:1.1.1.1", max_requests=1, window_seconds=60)
    assert blocked is False

    await limiter.clear()
    allowed_again, retry_after = await limiter.acquire(
        "login:1.1.1.1",
        max_requests=1,
        window_seconds=60,
    )
    assert allowed_again is True
    assert retry_after == 0


def test_get_rate_limiter_uses_redis_backend_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedisLimiter:
        def __init__(self, *, redis_url: str, namespace: str) -> None:
            self.redis_url = redis_url
            self.namespace = namespace

        async def acquire(
            self,
            key: str,
            *,
            max_requests: int,
            window_seconds: int,
        ) -> tuple[bool, int]:
            return True, 0

        async def clear(self) -> None:
            return None

    settings = SimpleNamespace(
        auth_rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
        auth_rate_limit_redis_namespace="auth_limit_test",
    )
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    monkeypatch.setattr(rate_limit_module, "RedisSlidingWindowRateLimiter", FakeRedisLimiter)
    monkeypatch.setattr(rate_limit_module, "_rate_limiter", None)
    monkeypatch.setattr(rate_limit_module, "_rate_limiter_signature", None)

    limiter = rate_limit_module.get_rate_limiter()
    assert isinstance(limiter, FakeRedisLimiter)
    assert limiter.redis_url == "redis://redis:6379/0"
    assert limiter.namespace == "auth_limit_test"


def test_get_rate_limiter_reuses_instance_for_same_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        auth_rate_limit_backend="memory",
        redis_url=None,
        auth_rate_limit_redis_namespace="auth_rate_limit",
    )
    monkeypatch.setattr(rate_limit_module, "get_settings", lambda: settings)
    monkeypatch.setattr(rate_limit_module, "_rate_limiter", None)
    monkeypatch.setattr(rate_limit_module, "_rate_limiter_signature", None)

    first = rate_limit_module.get_rate_limiter()
    second = rate_limit_module.get_rate_limiter()

    assert first is second


def test_get_rate_limiter_rebuilds_when_signature_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedisLimiter:
        def __init__(self, *, redis_url: str, namespace: str) -> None:
            self.redis_url = redis_url
            self.namespace = namespace

        async def acquire(
            self,
            key: str,
            *,
            max_requests: int,
            window_seconds: int,
        ) -> tuple[bool, int]:
            return True, 0

        async def clear(self) -> None:
            return None

    state = {
        "backend": "memory",
        "redis_url": None,
        "namespace": "auth_rate_limit",
    }

    def _settings() -> SimpleNamespace:
        return SimpleNamespace(
            auth_rate_limit_backend=state["backend"],
            redis_url=state["redis_url"],
            auth_rate_limit_redis_namespace=state["namespace"],
        )

    monkeypatch.setattr(rate_limit_module, "get_settings", _settings)
    monkeypatch.setattr(rate_limit_module, "RedisSlidingWindowRateLimiter", FakeRedisLimiter)
    monkeypatch.setattr(rate_limit_module, "_rate_limiter", None)
    monkeypatch.setattr(rate_limit_module, "_rate_limiter_signature", None)

    first = rate_limit_module.get_rate_limiter()

    state["backend"] = "redis"
    state["redis_url"] = "redis://redis:6379/0"
    state["namespace"] = "auth_limit_test_v2"
    second = rate_limit_module.get_rate_limiter()

    assert first is not second
    assert isinstance(second, FakeRedisLimiter)
