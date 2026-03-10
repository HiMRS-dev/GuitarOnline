from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.modules.identity.rate_limit import (
    enforce_login_rate_limit,
    enforce_refresh_rate_limit,
    enforce_register_rate_limit,
)
from app.modules.identity.router import router
from app.modules.identity.schemas import LoginRequest, TokenPair
from app.modules.identity.service import get_identity_service


class FakeIdentityService:
    def __init__(self) -> None:
        self.refresh_inputs: list[str] = []
        self.revoked_inputs: list[str] = []

    async def login(self, _: LoginRequest) -> TokenPair:
        return TokenPair(
            access_token="initial-access-token",
            refresh_token="initial-refresh-token",
        )

    async def refresh_tokens(self, refresh_token_value: str) -> TokenPair:
        self.refresh_inputs.append(refresh_token_value)
        return TokenPair(
            access_token="rotated-access-token",
            refresh_token="rotated-refresh-token",
        )

    async def revoke_refresh_token(self, refresh_token_value: str) -> None:
        self.revoked_inputs.append(refresh_token_value)


def _build_client(service: FakeIdentityService) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_identity_service] = lambda: service
    app.dependency_overrides[enforce_register_rate_limit] = lambda: None
    app.dependency_overrides[enforce_login_rate_limit] = lambda: None
    app.dependency_overrides[enforce_refresh_rate_limit] = lambda: None
    return TestClient(app)


def test_login_sets_httponly_refresh_cookie() -> None:
    settings = get_settings()
    service = FakeIdentityService()
    client = _build_client(service)

    response = client.post(
        "/api/v1/identity/auth/login",
        json={"email": "admin@guitaronline.dev", "password": "StrongPass123!"},
    )

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert f"{settings.auth_refresh_cookie_name}=initial-refresh-token" in set_cookie
    assert "HttpOnly" in set_cookie
    if settings.auth_refresh_cookie_secure:
        assert "Secure" in set_cookie


def test_refresh_uses_cookie_when_request_body_is_missing() -> None:
    settings = get_settings()
    service = FakeIdentityService()
    client = _build_client(service)
    client.cookies.set(settings.auth_refresh_cookie_name, "cookie-refresh-token")

    response = client.post("/api/v1/identity/auth/refresh")

    assert response.status_code == 200
    assert service.refresh_inputs == ["cookie-refresh-token"]
    assert response.json()["access_token"] == "rotated-access-token"
    assert (
        f"{settings.auth_refresh_cookie_name}=rotated-refresh-token"
        in response.headers.get("set-cookie", "")
    )


def test_refresh_prefers_request_body_over_cookie_for_legacy_clients() -> None:
    settings = get_settings()
    service = FakeIdentityService()
    client = _build_client(service)
    client.cookies.set(settings.auth_refresh_cookie_name, "cookie-refresh-token")

    response = client.post(
        "/api/v1/identity/auth/refresh",
        json={"refresh_token": "body-refresh-token"},
    )

    assert response.status_code == 200
    assert service.refresh_inputs == ["body-refresh-token"]


def test_logout_revokes_token_and_clears_cookie() -> None:
    settings = get_settings()
    service = FakeIdentityService()
    client = _build_client(service)
    client.cookies.set(settings.auth_refresh_cookie_name, "logout-refresh-token")

    response = client.post("/api/v1/identity/auth/logout")

    assert response.status_code == 204
    assert service.revoked_inputs == ["logout-refresh-token"]
    cleared_cookie = response.headers.get("set-cookie", "")
    assert f"{settings.auth_refresh_cookie_name}=" in cleared_cookie
    assert "Max-Age=0" in cleared_cookie or "max-age=0" in cleared_cookie
