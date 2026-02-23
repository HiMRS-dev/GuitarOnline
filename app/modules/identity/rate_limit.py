"""Rate-limit dependencies for identity endpoints."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import Request

from app.core.config import get_settings
from app.core.rate_limit import get_rate_limiter
from app.shared.exceptions import RateLimitException


def _trusted_proxy_ips(raw_value: object) -> set[str]:
    if raw_value is None:
        return set()
    if isinstance(raw_value, str):
        values: Iterable[object] = raw_value.split(",")
    elif isinstance(raw_value, tuple | list | set | frozenset):
        values = raw_value
    else:
        return set()

    return {str(value).strip() for value in values if str(value).strip()}


def _resolve_client_ip(request: Request, *, trusted_proxy_ips: set[str]) -> str:
    client_ip = "unknown"
    if request.client and request.client.host:
        client_ip = request.client.host

    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return client_ip
    if client_ip not in trusted_proxy_ips:
        return client_ip

    forwarded_client = forwarded_for.split(",")[0].strip()
    return forwarded_client or client_ip


async def _enforce_limit(request: Request, *, action: str, max_requests: int) -> None:
    settings = get_settings()
    resolved_ip = _resolve_client_ip(
        request,
        trusted_proxy_ips=_trusted_proxy_ips(settings.auth_rate_limit_trusted_proxy_ips),
    )
    key = f"identity:{action}:{resolved_ip}"
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
