from __future__ import annotations

from collections import deque
from uuid import uuid4

import httpx
import pytest

from tests import integration_smoke_pool as smoke_pool


class FakeAsyncClient:
    def __init__(self, *, base_url: str, responses: list[httpx.Response]) -> None:
        self.base_url = httpx.URL(base_url)
        self._responses = deque(responses)
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []

    async def get(self, path: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        self.calls.append(("GET", path, headers, None))
        return self._responses.popleft()

    async def post(self, path: str, *, json: dict[str, str] | None = None) -> httpx.Response:
        self.calls.append(("POST", path, None, json))
        return self._responses.popleft()


def _response(
    method: str,
    url: str,
    status_code: int,
    *,
    json_body: dict | None = None,
) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status_code, json=json_body, request=request)


@pytest.mark.asyncio
async def test_login_smoke_portal_session_reuses_cached_session_when_me_succeeds() -> None:
    smoke_pool._PORTAL_SESSION_CACHE.clear()
    user_id = str(uuid4())
    base_url = "http://integration.test/api/v1"
    client = FakeAsyncClient(
        base_url=base_url,
        responses=[
            _response(
                "POST",
                f"{base_url}/identity/auth/login",
                200,
                json_body={"access_token": "token-a", "refresh_token": "refresh-a"},
            ),
            _response(
                "GET",
                f"{base_url}/identity/users/me",
                200,
                json_body={"id": user_id},
            ),
            _response(
                "GET",
                f"{base_url}/identity/users/me",
                200,
                json_body={"id": user_id},
            ),
        ],
    )

    first_session = await smoke_pool.login_smoke_portal_session(client, role="student")
    second_session = await smoke_pool.login_smoke_portal_session(client, role="student")

    assert first_session is second_session
    assert client.calls == [
        (
            "POST",
            "/identity/auth/login",
            None,
            {
                "email": "smoke-student-1@guitaronline.dev",
                "password": smoke_pool.TEST_SMOKE_POOL_PASSWORD,
            },
        ),
        (
            "GET",
            "/identity/users/me",
            {"Authorization": "Bearer token-a"},
            None,
        ),
        (
            "GET",
            "/identity/users/me",
            {"Authorization": "Bearer token-a"},
            None,
        ),
    ]


@pytest.mark.asyncio
async def test_login_smoke_portal_session_relogs_when_cached_session_is_rejected() -> None:
    smoke_pool._PORTAL_SESSION_CACHE.clear()
    user_id = str(uuid4())
    base_url = "http://integration.test/api/v1"
    client = FakeAsyncClient(
        base_url=base_url,
        responses=[
            _response(
                "POST",
                f"{base_url}/identity/auth/login",
                200,
                json_body={"access_token": "token-a", "refresh_token": "refresh-a"},
            ),
            _response(
                "GET",
                f"{base_url}/identity/users/me",
                200,
                json_body={"id": user_id},
            ),
            _response(
                "GET",
                f"{base_url}/identity/users/me",
                401,
                json_body={"error": {"code": "unauthorized", "message": "expired"}},
            ),
            _response(
                "POST",
                f"{base_url}/identity/auth/login",
                200,
                json_body={"access_token": "token-b", "refresh_token": "refresh-b"},
            ),
            _response(
                "GET",
                f"{base_url}/identity/users/me",
                200,
                json_body={"id": user_id},
            ),
        ],
    )

    first_session = await smoke_pool.login_smoke_portal_session(client, role="student")
    second_session = await smoke_pool.login_smoke_portal_session(client, role="student")

    assert first_session.access_token == "token-a"
    assert second_session.access_token == "token-b"
    assert client.calls == [
        (
            "POST",
            "/identity/auth/login",
            None,
            {
                "email": "smoke-student-1@guitaronline.dev",
                "password": smoke_pool.TEST_SMOKE_POOL_PASSWORD,
            },
        ),
        (
            "GET",
            "/identity/users/me",
            {"Authorization": "Bearer token-a"},
            None,
        ),
        (
            "GET",
            "/identity/users/me",
            {"Authorization": "Bearer token-a"},
            None,
        ),
        (
            "POST",
            "/identity/auth/login",
            None,
            {
                "email": "smoke-student-1@guitaronline.dev",
                "password": smoke_pool.TEST_SMOKE_POOL_PASSWORD,
            },
        ),
        (
            "GET",
            "/identity/users/me",
            {"Authorization": "Bearer token-b"},
            None,
        ),
    ]
