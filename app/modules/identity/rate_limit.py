"""Rate-limit dependencies for identity endpoints."""

from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings
from app.core.rate_limit import get_rate_limiter
from app.shared.exceptions import RateLimitException


def _resolve_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Use first IP from proxy chain.
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _enforce_limit(request: Request, *, action: str, max_requests: int) -> None:
    settings = get_settings()
    key = f"identity:{action}:{_resolve_client_ip(request)}"
    allowed, retry_after = await get_rate_limiter().acquire(
        key,
        max_requests=max_requests,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )
    if not allowed:
        raise RateLimitException(
            f"Too many {action} requests. Try again in {retry_after} second(s).",
        )


async def enforce_register_rate_limit(request: Request) -> None:
    """Apply rate limit for register endpoint."""
    settings = get_settings()
    await _enforce_limit(
        request,
        action="register",
        max_requests=settings.auth_rate_limit_register_requests,
    )


async def enforce_login_rate_limit(request: Request) -> None:
    """Apply rate limit for login endpoint."""
    settings = get_settings()
    await _enforce_limit(
        request,
        action="login",
        max_requests=settings.auth_rate_limit_login_requests,
    )


async def enforce_refresh_rate_limit(request: Request) -> None:
    """Apply rate limit for refresh endpoint."""
    settings = get_settings()
    await _enforce_limit(
        request,
        action="refresh",
        max_requests=settings.auth_rate_limit_refresh_requests,
    )
