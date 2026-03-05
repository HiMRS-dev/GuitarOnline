"""Integration RBAC checks for 401/403/200 role paths."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

API_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
HEALTHCHECK_URL = os.getenv("INTEGRATION_HEALTH_URL", "http://localhost:8000/health")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))

_INTEGRATION_STACK_HEALTHY: bool | None = None
_INTEGRATION_STACK_ERROR: str | None = None


@dataclass(slots=True)
class AuthUser:
    id: UUID
    access_token: str


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _assert_status(response: httpx.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"{response.request.method} {response.request.url} -> "
        f"{response.status_code}, body={response.text}"
    )


async def _register_and_login(client: httpx.AsyncClient, role: str) -> AuthUser:
    email = f"rbac-{role}-{uuid4().hex}@guitaronline.dev"
    password = "StrongPass123!"

    register_response = await client.post(
        "/identity/auth/register",
        json={
            "email": email,
            "password": password,
            "timezone": "UTC",
            "role": role,
        },
    )
    _assert_status(register_response, 201)
    user_id = UUID(register_response.json()["id"])

    login_response = await client.post(
        "/identity/auth/login",
        json={"email": email, "password": password},
    )
    _assert_status(login_response, 200)
    access_token = login_response.json()["access_token"]

    return AuthUser(id=user_id, access_token=access_token)


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
async def test_admin_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/admin/kpi/overview")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/kpi/overview",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/kpi/overview",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)


@pytest.mark.asyncio
async def test_admin_teachers_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/admin/teachers")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/teachers",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/teachers",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_admin_teacher_detail_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    create_profile_response = await api_client.post(
        "/teachers/profiles",
        headers=_auth_headers(teacher.access_token),
        json={
            "user_id": str(teacher.id),
            "display_name": "Teacher For Admin Detail",
            "bio": "test",
            "experience_years": 3,
        },
    )
    _assert_status(create_profile_response, 201)

    no_token_response = await api_client.get(f"/admin/teachers/{teacher.id}")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        f"/admin/teachers/{teacher.id}",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        f"/admin/teachers/{teacher.id}",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert payload["teacher_id"] == str(teacher.id)
    assert payload["status"] in {"pending", "verified", "disabled"}


@pytest.mark.asyncio
async def test_admin_teacher_verify_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    create_profile_response = await api_client.post(
        "/teachers/profiles",
        headers=_auth_headers(teacher.access_token),
        json={
            "user_id": str(teacher.id),
            "display_name": "Teacher For Verify",
            "bio": "test",
            "experience_years": 3,
        },
    )
    _assert_status(create_profile_response, 201)

    no_token_response = await api_client.post(f"/admin/teachers/{teacher.id}/verify")
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/admin/teachers/{teacher.id}/verify",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        f"/admin/teachers/{teacher.id}/verify",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert payload["teacher_id"] == str(teacher.id)
    assert payload["status"] == "verified"
    assert payload["verified"] is True


@pytest.mark.asyncio
async def test_admin_teacher_disable_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    create_profile_response = await api_client.post(
        "/teachers/profiles",
        headers=_auth_headers(teacher.access_token),
        json={
            "user_id": str(teacher.id),
            "display_name": "Teacher For Disable",
            "bio": "test",
            "experience_years": 3,
        },
    )
    _assert_status(create_profile_response, 201)

    no_token_response = await api_client.post(f"/admin/teachers/{teacher.id}/disable")
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/admin/teachers/{teacher.id}/disable",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        f"/admin/teachers/{teacher.id}/disable",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert payload["teacher_id"] == str(teacher.id)
    assert payload["status"] == "disabled"
    assert payload["verified"] is False
    assert payload["is_active"] is False


@pytest.mark.asyncio
async def test_admin_teacher_moderation_endpoints_write_audit_logs(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    teacher = await _register_and_login(api_client, "teacher")

    create_profile_response = await api_client.post(
        "/teachers/profiles",
        headers=_auth_headers(teacher.access_token),
        json={
            "user_id": str(teacher.id),
            "display_name": "Teacher For Audit",
            "bio": "test",
            "experience_years": 3,
        },
    )
    _assert_status(create_profile_response, 201)

    verify_response = await api_client.post(
        f"/admin/teachers/{teacher.id}/verify",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(verify_response, 200)

    disable_response = await api_client.post(
        f"/admin/teachers/{teacher.id}/disable",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(disable_response, 200)

    logs_response = await api_client.get(
        "/audit/logs?limit=100&offset=0",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(logs_response, 200)

    items = logs_response.json()["items"]
    actions_for_teacher = {
        item["action"]
        for item in items
        if item.get("payload", {}).get("teacher_id") == str(teacher.id)
    }
    assert "admin.teacher.verify" in actions_for_teacher
    assert "admin.teacher.disable" in actions_for_teacher


@pytest.mark.asyncio
async def test_admin_slots_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/admin/slots")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/slots",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_teacher_profile_create_forbidden_for_student_and_allowed_for_teacher(
    api_client: httpx.AsyncClient,
) -> None:
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    forbidden_response = await api_client.post(
        "/teachers/profiles",
        headers=_auth_headers(student.access_token),
        json={
            "user_id": str(student.id),
            "display_name": "Student Should Be Forbidden",
            "bio": "test",
            "experience_years": 1,
        },
    )
    _assert_status(forbidden_response, 403)

    teacher_response = await api_client.post(
        "/teachers/profiles",
        headers=_auth_headers(teacher.access_token),
        json={
            "user_id": str(teacher.id),
            "display_name": "Teacher Self Profile",
            "bio": "test",
            "experience_years": 5,
        },
    )
    _assert_status(teacher_response, 201)


@pytest.mark.asyncio
async def test_booking_hold_requires_student_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    package_response = await api_client.post(
        "/billing/packages",
        headers=_auth_headers(admin.access_token),
        json={
            "student_id": str(student.id),
            "lessons_total": 4,
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    _assert_status(package_response, 201)
    package_id = package_response.json()["id"]

    start_at = datetime.now(UTC) + timedelta(days=2)
    end_at = start_at + timedelta(hours=1)
    slot_response = await api_client.post(
        "/scheduling/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        },
    )
    _assert_status(slot_response, 201)
    slot_id = slot_response.json()["id"]

    teacher_hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(teacher.access_token),
        json={"slot_id": slot_id, "package_id": package_id},
    )
    _assert_status(teacher_hold_response, 403)

    student_hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot_id, "package_id": package_id},
    )
    _assert_status(student_hold_response, 200)
