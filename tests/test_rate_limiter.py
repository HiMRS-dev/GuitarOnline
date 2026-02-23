from __future__ import annotations

import pytest

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
