from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.rate_limit import InMemorySlidingWindowRateLimiter
from app.modules.identity import rate_limit as identity_rate_limit
from app.shared.exceptions import RateLimitException


def _make_request(
    *,
    client_ip: str = "10.0.0.1",
    x_forwarded_for: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if x_forwarded_for is not None:
        headers.append((b"x-forwarded-for", x_forwarded_for.encode()))

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/identity/auth/login",
        "headers": headers,
        "client": (client_ip, 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_register_rate_limit_blocks_after_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    now_point = [1000.0]
    limiter = InMemorySlidingWindowRateLimiter(now_provider=lambda: now_point[0])
    settings = SimpleNamespace(
        auth_rate_limit_window_seconds=60,
        auth_rate_limit_register_requests=2,
        auth_rate_limit_login_requests=10,
        auth_rate_limit_refresh_requests=20,
    )

    monkeypatch.setattr(identity_rate_limit, "get_rate_limiter", lambda: limiter)
    monkeypatch.setattr(identity_rate_limit, "get_settings", lambda: settings)

    request = _make_request(client_ip="127.0.0.1")
    await identity_rate_limit.enforce_register_rate_limit(request)
    await identity_rate_limit.enforce_register_rate_limit(request)
    with pytest.raises(RateLimitException):
        await identity_rate_limit.enforce_register_rate_limit(request)


@pytest.mark.asyncio
async def test_login_rate_limit_uses_forwarded_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class CapturingLimiter:
        async def acquire(
            self,
            key: str,
            *,
            max_requests: int,
            window_seconds: int,
        ) -> tuple[bool, int]:
            captured["key"] = key
            captured["max_requests"] = str(max_requests)
            captured["window_seconds"] = str(window_seconds)
            return True, 0

    settings = SimpleNamespace(
        auth_rate_limit_window_seconds=120,
        auth_rate_limit_register_requests=5,
        auth_rate_limit_login_requests=7,
        auth_rate_limit_refresh_requests=20,
    )
    monkeypatch.setattr(identity_rate_limit, "get_rate_limiter", lambda: CapturingLimiter())
    monkeypatch.setattr(identity_rate_limit, "get_settings", lambda: settings)

    request = _make_request(client_ip="127.0.0.1", x_forwarded_for="2.2.2.2, 3.3.3.3")
    await identity_rate_limit.enforce_login_rate_limit(request)

    assert captured["key"] == "identity:login:2.2.2.2"
    assert captured["max_requests"] == "7"
    assert captured["window_seconds"] == "120"


@pytest.mark.asyncio
async def test_refresh_rate_limit_is_independent_from_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now_point = [2000.0]
    limiter = InMemorySlidingWindowRateLimiter(now_provider=lambda: now_point[0])
    settings = SimpleNamespace(
        auth_rate_limit_window_seconds=30,
        auth_rate_limit_register_requests=5,
        auth_rate_limit_login_requests=1,
        auth_rate_limit_refresh_requests=1,
    )
    monkeypatch.setattr(identity_rate_limit, "get_rate_limiter", lambda: limiter)
    monkeypatch.setattr(identity_rate_limit, "get_settings", lambda: settings)

    request = _make_request(client_ip="10.10.10.10")
    await identity_rate_limit.enforce_login_rate_limit(request)
    with pytest.raises(RateLimitException):
        await identity_rate_limit.enforce_login_rate_limit(request)

    # Refresh has separate key and should pass once.
    await identity_rate_limit.enforce_refresh_rate_limit(request)
