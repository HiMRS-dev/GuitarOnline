"""Integration tests for portal-oriented API endpoint sequences."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

API_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:18000/api/v1").rstrip("/")
HEALTHCHECK_URL = os.getenv("INTEGRATION_HEALTH_URL", "http://localhost:18000/health")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))
INTEGRATION_ADMIN_EMAIL = os.getenv(
    "INTEGRATION_ADMIN_EMAIL",
    os.getenv("TEST_BOOTSTRAP_ADMIN_EMAIL", "bootstrap-admin@guitaronline.dev"),
).strip()
INTEGRATION_ADMIN_PASSWORD = os.getenv(
    "INTEGRATION_ADMIN_PASSWORD",
    os.getenv("TEST_BOOTSTRAP_ADMIN_PASSWORD", ""),
)

_INTEGRATION_STACK_HEALTHY: bool | None = None
_INTEGRATION_STACK_ERROR: str | None = None


@dataclass(slots=True)
class PortalAuthSession:
    user_id: UUID
    access_token: str
    refresh_token: str


def _assert_status(response: httpx.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"{response.request.method} {response.request.url} -> "
        f"{response.status_code}, body={response.text}"
    )


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _login_with_retry(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
) -> httpx.Response:
    last_response: httpx.Response | None = None

    for _ in range(6):
        response = await client.post(
            "/identity/auth/login",
            json={"email": email, "password": password},
        )
        if response.status_code == 200:
            return response
        if response.status_code != 403 or "Invalid credentials" not in response.text:
            return response
        last_response = response
        await asyncio.sleep(0.1)

    assert last_response is not None
    return last_response


async def _register_and_login(client: httpx.AsyncClient, role: str) -> PortalAuthSession:
    email = f"portal-{role}-{uuid4().hex}@guitaronline.dev"
    password = "StrongPass123!"

    register_response = await client.post(
        "/identity/auth/register",
        json={
            "email": email,
            "password": password,
            "timezone": "UTC",
        },
    )
    _assert_status(register_response, 201)
    user_id = UUID(register_response.json()["id"])

    login_response = await _login_with_retry(
        client,
        email=email,
        password=password,
    )
    _assert_status(login_response, 200)
    token_pair = login_response.json()

    session = PortalAuthSession(
        user_id=user_id,
        access_token=token_pair["access_token"],
        refresh_token=token_pair["refresh_token"],
    )
    return await _ensure_role(client, session, role=role)


async def _login_existing_admin(client: httpx.AsyncClient) -> PortalAuthSession:
    login_response = await client.post(
        "/identity/auth/login",
        json={
            "email": INTEGRATION_ADMIN_EMAIL,
            "password": INTEGRATION_ADMIN_PASSWORD,
        },
    )
    if login_response.status_code != 200:
        pytest.skip(
            "Bootstrap admin credentials are unavailable for integration role reassignment "
            f"({INTEGRATION_ADMIN_EMAIL}).",
        )
        raise AssertionError("unreachable")

    token_pair = login_response.json()
    me_response = await client.get(
        "/identity/users/me",
        headers=_auth_headers(token_pair["access_token"]),
    )
    _assert_status(me_response, 200)
    return PortalAuthSession(
        user_id=UUID(me_response.json()["id"]),
        access_token=token_pair["access_token"],
        refresh_token=token_pair["refresh_token"],
    )


async def _ensure_role(
    client: httpx.AsyncClient,
    session: PortalAuthSession,
    *,
    role: str,
) -> PortalAuthSession:
    if role == "student":
        return session

    bootstrap_admin = await _login_existing_admin(client)
    role_change_response = await client.post(
        f"/admin/users/{session.user_id}/role",
        headers=_auth_headers(bootstrap_admin.access_token),
        json={"role": role},
    )
    _assert_status(role_change_response, 200)
    return session


@pytest_asyncio.fixture()
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    global _INTEGRATION_STACK_HEALTHY, _INTEGRATION_STACK_ERROR  # noqa: PLW0603

    if _INTEGRATION_STACK_HEALTHY is None:
        probe_timeout_seconds = min(REQUEST_TIMEOUT_SECONDS, 3.0)
        async with httpx.AsyncClient(timeout=probe_timeout_seconds) as probe:
            try:
                health_response = await probe.get(HEALTHCHECK_URL)
            except httpx.HTTPError as exc:
                _INTEGRATION_STACK_HEALTHY = False
                _INTEGRATION_STACK_ERROR = (
                    f"Integration stack unavailable at {HEALTHCHECK_URL}: {exc}"
                )
            else:
                if health_response.status_code != 200:
                    _INTEGRATION_STACK_HEALTHY = False
                    _INTEGRATION_STACK_ERROR = (
                        f"Integration stack returned {health_response.status_code} "
                        f"for {HEALTHCHECK_URL}"
                    )
                else:
                    _INTEGRATION_STACK_HEALTHY = True
                    _INTEGRATION_STACK_ERROR = None

    if not _INTEGRATION_STACK_HEALTHY:
        pytest.skip(_INTEGRATION_STACK_ERROR or "Integration stack is unavailable")
        return

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        yield client


@pytest.mark.asyncio
async def test_portal_student_sequence_register_login_refresh_and_data_endpoints(
    api_client: httpx.AsyncClient,
) -> None:
    student = await _register_and_login(api_client, "student")

    me_response = await api_client.get(
        "/identity/users/me",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(me_response, 200)
    me_payload = me_response.json()
    assert me_payload["id"] == str(student.user_id)
    assert me_payload["role"]["name"] == "student"

    slots_response = await api_client.get(
        "/scheduling/slots/open",
        params={"limit": 20, "offset": 0},
    )
    _assert_status(slots_response, 200)
    assert isinstance(slots_response.json()["items"], list)

    bookings_response = await api_client.get(
        "/booking/my",
        headers=_auth_headers(student.access_token),
        params={"limit": 20, "offset": 0},
    )
    _assert_status(bookings_response, 200)
    assert isinstance(bookings_response.json()["items"], list)

    packages_response = await api_client.get(
        f"/billing/packages/students/{student.user_id}",
        headers=_auth_headers(student.access_token),
        params={"limit": 20, "offset": 0},
    )
    _assert_status(packages_response, 200)
    assert isinstance(packages_response.json()["items"], list)

    refresh_response = await api_client.post(
        "/identity/auth/refresh",
        json={"refresh_token": student.refresh_token},
    )
    _assert_status(refresh_response, 200)
    refreshed_access_token = refresh_response.json()["access_token"]

    me_after_refresh_response = await api_client.get(
        "/identity/users/me",
        headers=_auth_headers(refreshed_access_token),
    )
    _assert_status(me_after_refresh_response, 200)
    assert me_after_refresh_response.json()["id"] == str(student.user_id)


@pytest.mark.asyncio
async def test_portal_teacher_and_admin_sequences_for_role_specific_endpoints(
    api_client: httpx.AsyncClient,
) -> None:
    teacher = await _ensure_role(
        api_client,
        await _register_and_login(api_client, "teacher"),
        role="teacher",
    )
    admin = await _ensure_role(
        api_client,
        await _register_and_login(api_client, "admin"),
        role="admin",
    )

    lessons_response = await api_client.get(
        "/teacher/lessons",
        headers=_auth_headers(teacher.access_token),
        params={"limit": 20, "offset": 0},
    )
    _assert_status(lessons_response, 200)
    assert isinstance(lessons_response.json()["items"], list)

    expire_holds_response = await api_client.post(
        "/booking/holds/expire",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(expire_holds_response, 200)
    assert isinstance(expire_holds_response.json(), int)

    expire_packages_response = await api_client.post(
        "/billing/packages/expire",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(expire_packages_response, 200)
    assert isinstance(expire_packages_response.json(), int)
