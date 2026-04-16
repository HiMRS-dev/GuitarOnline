"""Integration RBAC checks for 401/403/200 role paths."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio

from tests.integration_smoke_pool import AuthUser, login_smoke_auth_user, reset_test_smoke_pool

API_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:18000/api/v1").rstrip("/")
HEALTHCHECK_URL = os.getenv("INTEGRATION_HEALTH_URL", "http://localhost:18000/health")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))

_INTEGRATION_STACK_HEALTHY: bool | None = None
_INTEGRATION_STACK_ERROR: str | None = None


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _assert_status(response: httpx.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"{response.request.method} {response.request.url} -> "
        f"{response.status_code}, body={response.text}"
    )


async def _register_and_login(client: httpx.AsyncClient, role: str) -> AuthUser:
    return await login_smoke_auth_user(client, role=role)


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


@pytest_asyncio.fixture(autouse=True)
async def smoke_pool_reset(api_client: httpx.AsyncClient) -> AsyncIterator[None]:
    reset_test_smoke_pool()
    yield


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
async def test_admin_sales_kpi_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    from_utc = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    to_utc = datetime.now(UTC).isoformat()

    no_token_response = await api_client.get(
        "/admin/kpi/sales",
        params={"from_utc": from_utc, "to_utc": to_utc},
    )
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/kpi/sales",
        headers=_auth_headers(student.access_token),
        params={"from_utc": from_utc, "to_utc": to_utc},
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/kpi/sales",
        headers=_auth_headers(admin.access_token),
        params={"from_utc": from_utc, "to_utc": to_utc},
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert "payments_succeeded_amount" in payload
    assert "packages_created_total" in payload


@pytest.mark.asyncio
async def test_teacher_lessons_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/teacher/lessons")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/teacher/lessons",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    teacher_response = await api_client.get(
        "/teacher/lessons",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_response, 200)
    payload = teacher_response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_teacher_students_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/booking/teacher/students")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/booking/teacher/students",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    teacher_response = await api_client.get(
        "/booking/teacher/students",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_response, 200)
    payload = teacher_response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_teacher_schedule_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/scheduling/teachers/me/schedule")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/scheduling/teachers/me/schedule",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    teacher_response = await api_client.get(
        "/scheduling/teachers/me/schedule",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_response, 200)
    payload = teacher_response.json()
    assert payload["teacher_id"] == str(teacher.id)
    assert "windows" in payload
    assert isinstance(payload["windows"], list)


@pytest.mark.asyncio
async def test_me_lessons_alias_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/me/lessons")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/me/lessons",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 200)
    student_payload = student_response.json()
    assert "items" in student_payload
    assert isinstance(student_payload["items"], list)

    teacher_response = await api_client.get(
        "/me/lessons",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_response, 403)


@pytest.mark.asyncio
async def test_lessons_my_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/lessons/my")
    _assert_status(no_token_response, 401)

    teacher_response = await api_client.get(
        "/lessons/my",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_response, 403)

    student_response = await api_client.get(
        "/lessons/my",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 200)
    student_payload = student_response.json()
    assert "items" in student_payload
    assert isinstance(student_payload["items"], list)


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
    assert payload["status"] in {"active", "disabled"}


@pytest.mark.asyncio
async def test_admin_teacher_disable_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

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
    assert payload["is_active"] is False


@pytest.mark.asyncio
async def test_admin_teacher_moderation_endpoints_write_audit_logs(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    teacher = await _register_and_login(api_client, "teacher")

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
async def test_admin_bookings_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/admin/bookings")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/bookings",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/bookings",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_admin_packages_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/admin/packages")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/packages",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/packages",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_admin_notifications_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/admin/notifications")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/notifications",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/notifications",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_admin_create_package_endpoint_returns_401_403_and_201_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    payload = {
        "student_id": str(student.id),
        "lessons_total": 8,
        "expires_at_utc": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "price_amount": "149.00",
        "price_currency": "usd",
    }

    no_token_response = await api_client.post("/admin/packages", json=payload)
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        "/admin/packages",
        headers=_auth_headers(student.access_token),
        json=payload,
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        "/admin/packages",
        headers=_auth_headers(admin.access_token),
        json=payload,
    )
    _assert_status(admin_response, 201)
    body = admin_response.json()
    assert body["student_id"] == str(student.id)
    assert body["price_amount"] == "149.00"
    assert body["price_currency"] == "USD"
    assert body["lessons_reserved"] == 0


@pytest.mark.asyncio
async def test_admin_cancel_package_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    create_payload = {
        "student_id": str(student.id),
        "lessons_total": 6,
        "expires_at_utc": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "price_amount": "149.00",
        "price_currency": "USD",
    }

    create_response = await api_client.post(
        "/admin/packages",
        headers=_auth_headers(admin.access_token),
        json=create_payload,
    )
    _assert_status(create_response, 201)
    package_id = create_response.json()["package_id"]

    no_token_response = await api_client.post(f"/admin/packages/{package_id}/cancel")
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/admin/packages/{package_id}/cancel",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        f"/admin/packages/{package_id}/cancel",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    body = admin_response.json()
    assert body["package_id"] == package_id
    assert body["status"] == "canceled"

    second_cancel_response = await api_client.post(
        f"/admin/packages/{package_id}/cancel",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(second_cancel_response, 200)
    assert second_cancel_response.json()["status"] == "canceled"


@pytest.mark.asyncio
async def test_admin_cancel_booking_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    package_response = await api_client.post(
        "/billing/packages",
        headers=_auth_headers(admin.access_token),
        json={
            "student_id": str(student.id),
            "lessons_total": 5,
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    _assert_status(package_response, 201)
    package_id = package_response.json()["id"]

    start_at = datetime.now(UTC) + timedelta(days=8, hours=1)
    end_at = start_at + timedelta(hours=1)
    create_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": start_at.isoformat(),
            "end_at_utc": end_at.isoformat(),
        },
    )
    _assert_status(create_slot_response, 201)
    slot_id = create_slot_response.json()["slot_id"]

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot_id, "package_id": package_id},
    )
    _assert_status(hold_response, 200)
    booking_id = hold_response.json()["id"]

    confirm_response = await api_client.post(
        f"/booking/{booking_id}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(confirm_response, 200)

    no_token_response = await api_client.post(
        f"/admin/bookings/{booking_id}/cancel",
        json={"reason": "Admin replan"},
    )
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/admin/bookings/{booking_id}/cancel",
        headers=_auth_headers(student.access_token),
        json={"reason": "Admin replan"},
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        f"/admin/bookings/{booking_id}/cancel",
        headers=_auth_headers(admin.access_token),
        json={"reason": "Admin replan"},
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert payload["id"] == booking_id
    assert payload["status"] == "canceled"
    assert payload["cancellation_reason"] == "Admin replan"


@pytest.mark.asyncio
async def test_admin_reschedule_booking_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    package_response = await api_client.post(
        "/billing/packages",
        headers=_auth_headers(admin.access_token),
        json={
            "student_id": str(student.id),
            "lessons_total": 5,
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    _assert_status(package_response, 201)
    package_id = package_response.json()["id"]

    old_start_at = datetime.now(UTC) + timedelta(days=9, hours=1)
    old_end_at = old_start_at + timedelta(hours=1)
    old_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": old_start_at.isoformat(),
            "end_at_utc": old_end_at.isoformat(),
        },
    )
    _assert_status(old_slot_response, 201)
    old_slot_id = old_slot_response.json()["slot_id"]

    new_start_at = datetime.now(UTC) + timedelta(days=10, hours=1)
    new_end_at = new_start_at + timedelta(hours=1)
    new_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": new_start_at.isoformat(),
            "end_at_utc": new_end_at.isoformat(),
        },
    )
    _assert_status(new_slot_response, 201)
    new_slot_id = new_slot_response.json()["slot_id"]

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": old_slot_id, "package_id": package_id},
    )
    _assert_status(hold_response, 200)
    old_booking_id = hold_response.json()["id"]

    confirm_response = await api_client.post(
        f"/booking/{old_booking_id}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(confirm_response, 200)

    no_token_response = await api_client.post(
        f"/admin/bookings/{old_booking_id}/reschedule",
        json={"new_slot_id": new_slot_id, "reason": "Admin swap"},
    )
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/admin/bookings/{old_booking_id}/reschedule",
        headers=_auth_headers(student.access_token),
        json={"new_slot_id": new_slot_id, "reason": "Admin swap"},
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        f"/admin/bookings/{old_booking_id}/reschedule",
        headers=_auth_headers(admin.access_token),
        json={"new_slot_id": new_slot_id, "reason": "Admin swap"},
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert payload["status"] == "confirmed"
    assert payload["slot_id"] == new_slot_id
    assert payload["rescheduled_from_booking_id"] == old_booking_id
    assert payload["cancellation_reason"] is None


@pytest.mark.asyncio
async def test_admin_lesson_no_show_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    package_response = await api_client.post(
        "/billing/packages",
        headers=_auth_headers(admin.access_token),
        json={
            "student_id": str(student.id),
            "lessons_total": 5,
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    _assert_status(package_response, 201)
    package_id = package_response.json()["id"]

    start_at = datetime.now(UTC) + timedelta(days=11, hours=1)
    end_at = start_at + timedelta(hours=1)
    create_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": start_at.isoformat(),
            "end_at_utc": end_at.isoformat(),
        },
    )
    _assert_status(create_slot_response, 201)
    slot_id = create_slot_response.json()["slot_id"]

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot_id, "package_id": package_id},
    )
    _assert_status(hold_response, 200)
    booking_id = hold_response.json()["id"]

    confirm_response = await api_client.post(
        f"/booking/{booking_id}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(confirm_response, 200)

    teacher_lessons_response = await api_client.get(
        "/teacher/lessons?limit=20&offset=0",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_lessons_response, 200)
    lesson_items = teacher_lessons_response.json()["items"]
    lesson_id = next(
        item["id"] for item in lesson_items if item.get("booking_id") == booking_id
    )

    no_token_response = await api_client.post(f"/admin/lessons/{lesson_id}/no-show")
    _assert_status(no_token_response, 401)

    teacher_response = await api_client.post(
        f"/admin/lessons/{lesson_id}/no-show",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_response, 403)

    admin_response = await api_client.post(
        f"/admin/lessons/{lesson_id}/no-show",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert payload["id"] == lesson_id
    assert payload["status"] == "no_show"


@pytest.mark.asyncio
async def test_lesson_complete_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    package_response = await api_client.post(
        "/admin/packages",
        headers=_auth_headers(admin.access_token),
        json={
            "student_id": str(student.id),
            "lessons_total": 5,
            "expires_at_utc": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "price_amount": "149.00",
            "price_currency": "USD",
        },
    )
    _assert_status(package_response, 201)
    package_id = package_response.json()["package_id"]

    start_at = datetime.now(UTC) + timedelta(days=12, hours=1)
    end_at = start_at + timedelta(hours=1)
    create_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": start_at.isoformat(),
            "end_at_utc": end_at.isoformat(),
        },
    )
    _assert_status(create_slot_response, 201)
    slot_id = create_slot_response.json()["slot_id"]

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot_id, "package_id": package_id},
    )
    _assert_status(hold_response, 200)
    booking_id = hold_response.json()["id"]

    confirm_response = await api_client.post(
        f"/booking/{booking_id}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(confirm_response, 200)

    teacher_lessons_response = await api_client.get(
        "/teacher/lessons?limit=20&offset=0",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_lessons_response, 200)
    lesson_items = teacher_lessons_response.json()["items"]
    lesson_id = next(
        item["id"] for item in lesson_items if item.get("booking_id") == booking_id
    )

    no_token_response = await api_client.post(f"/lessons/{lesson_id}/complete")
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/lessons/{lesson_id}/complete",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    teacher_response = await api_client.post(
        f"/lessons/{lesson_id}/complete",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_response, 200)
    payload = teacher_response.json()
    assert payload["id"] == lesson_id
    assert payload["status"] == "completed"
    assert payload["consumed_at"] is not None


@pytest.mark.asyncio
async def test_teacher_lesson_report_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")

    package_response = await api_client.post(
        "/admin/packages",
        headers=_auth_headers(admin.access_token),
        json={
            "student_id": str(student.id),
            "lessons_total": 5,
            "expires_at_utc": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "price_amount": "149.00",
            "price_currency": "USD",
        },
    )
    _assert_status(package_response, 201)
    package_id = package_response.json()["package_id"]

    start_at = datetime.now(UTC) + timedelta(days=13, hours=1)
    end_at = start_at + timedelta(hours=1)
    create_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": start_at.isoformat(),
            "end_at_utc": end_at.isoformat(),
        },
    )
    _assert_status(create_slot_response, 201)
    slot_id = create_slot_response.json()["slot_id"]

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot_id, "package_id": package_id},
    )
    _assert_status(hold_response, 200)
    booking_id = hold_response.json()["id"]

    confirm_response = await api_client.post(
        f"/booking/{booking_id}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(confirm_response, 200)

    teacher_lessons_response = await api_client.get(
        "/teacher/lessons?limit=20&offset=0",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_lessons_response, 200)
    lesson_items = teacher_lessons_response.json()["items"]
    lesson_id = next(
        item["id"] for item in lesson_items if item.get("booking_id") == booking_id
    )

    payload = {
        "notes": "Progress report",
        "homework": "Practice C major scale",
        "links": ["https://example.com/homework"],
    }

    no_token_response = await api_client.post(
        f"/teacher/lessons/{lesson_id}/report",
        json=payload,
    )
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/teacher/lessons/{lesson_id}/report",
        headers=_auth_headers(student.access_token),
        json=payload,
    )
    _assert_status(student_response, 403)

    teacher_response = await api_client.post(
        f"/teacher/lessons/{lesson_id}/report",
        headers=_auth_headers(teacher.access_token),
        json=payload,
    )
    _assert_status(teacher_response, 200)
    updated = teacher_response.json()
    assert updated["id"] == lesson_id
    assert updated["notes"] == "Progress report"
    assert updated["homework"] == "Practice C major scale"
    assert updated["links"] == ["https://example.com/homework"]


@pytest.mark.asyncio
async def test_admin_slot_stats_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")

    no_token_response = await api_client.get("/admin/slots/stats")
    _assert_status(no_token_response, 401)

    student_response = await api_client.get(
        "/admin/slots/stats",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.get(
        "/admin/slots/stats",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert "total_slots" in payload
    assert "completed_slots" in payload


@pytest.mark.asyncio
async def test_admin_create_slot_endpoint_returns_401_403_and_201_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")
    start_at = datetime.now(UTC) + timedelta(days=3, hours=2)
    end_at = start_at + timedelta(hours=1)
    payload = {
        "teacher_id": str(teacher.id),
        "start_at_utc": start_at.isoformat(),
        "end_at_utc": end_at.isoformat(),
    }

    no_token_response = await api_client.post("/admin/slots", json=payload)
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(student.access_token),
        json=payload,
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json=payload,
    )
    _assert_status(admin_response, 201)
    body = admin_response.json()
    assert body["teacher_id"] == str(teacher.id)
    assert body["slot_status"] == "open"


@pytest.mark.asyncio
async def test_admin_bulk_create_slots_endpoint_returns_401_403_and_200_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")
    target_day = (datetime.now(UTC) + timedelta(days=7)).date()
    payload = {
        "teacher_id": str(teacher.id),
        "date_from_utc": target_day.isoformat(),
        "date_to_utc": target_day.isoformat(),
        "weekdays": [target_day.weekday()],
        "start_time_utc": "10:00:00",
        "end_time_utc": "12:00:00",
        "slot_duration_minutes": 60,
    }

    no_token_response = await api_client.post("/admin/slots/bulk-create", json=payload)
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        "/admin/slots/bulk-create",
        headers=_auth_headers(student.access_token),
        json=payload,
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        "/admin/slots/bulk-create",
        headers=_auth_headers(admin.access_token),
        json=payload,
    )
    _assert_status(admin_response, 200)
    body = admin_response.json()
    assert body["created_count"] >= 1
    assert isinstance(body["created_slot_ids"], list)


@pytest.mark.asyncio
async def test_admin_delete_slot_endpoint_returns_401_403_and_204_without_bookings(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")
    start_at = datetime.now(UTC) + timedelta(days=4, hours=1)
    end_at = start_at + timedelta(hours=1)

    create_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": start_at.isoformat(),
            "end_at_utc": end_at.isoformat(),
        },
    )
    _assert_status(create_response, 201)
    slot_id = create_response.json()["slot_id"]

    no_token_response = await api_client.delete(f"/admin/slots/{slot_id}")
    _assert_status(no_token_response, 401)

    student_response = await api_client.delete(
        f"/admin/slots/{slot_id}",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.delete(
        f"/admin/slots/{slot_id}",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_response, 204)


@pytest.mark.asyncio
async def test_admin_delete_slot_endpoint_returns_409_when_slot_has_related_booking(
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
            "lessons_total": 5,
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    _assert_status(package_response, 201)
    package_id = package_response.json()["id"]

    start_at = datetime.now(UTC) + timedelta(days=5, hours=1)
    end_at = start_at + timedelta(hours=1)
    create_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": start_at.isoformat(),
            "end_at_utc": end_at.isoformat(),
        },
    )
    _assert_status(create_slot_response, 201)
    slot_id = create_slot_response.json()["slot_id"]

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={
            "slot_id": slot_id,
            "package_id": package_id,
        },
    )
    _assert_status(hold_response, 200)

    delete_response = await api_client.delete(
        f"/admin/slots/{slot_id}",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(delete_response, 409)


@pytest.mark.asyncio
async def test_admin_block_slot_endpoint_returns_401_403_and_200_and_writes_audit(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    student = await _register_and_login(api_client, "student")
    teacher = await _register_and_login(api_client, "teacher")
    start_at = datetime.now(UTC) + timedelta(days=6, hours=1)
    end_at = start_at + timedelta(hours=1)
    create_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": start_at.isoformat(),
            "end_at_utc": end_at.isoformat(),
        },
    )
    _assert_status(create_slot_response, 201)
    slot_id = create_slot_response.json()["slot_id"]

    no_token_response = await api_client.post(
        f"/admin/slots/{slot_id}/block",
        json={"reason": "Teacher unavailable"},
    )
    _assert_status(no_token_response, 401)

    student_response = await api_client.post(
        f"/admin/slots/{slot_id}/block",
        headers=_auth_headers(student.access_token),
        json={"reason": "Teacher unavailable"},
    )
    _assert_status(student_response, 403)

    admin_response = await api_client.post(
        f"/admin/slots/{slot_id}/block",
        headers=_auth_headers(admin.access_token),
        json={"reason": "Teacher unavailable"},
    )
    _assert_status(admin_response, 200)
    payload = admin_response.json()
    assert payload["slot_id"] == slot_id
    assert payload["slot_status"] == "blocked"
    assert payload["block_reason"] == "Teacher unavailable"

    logs_response = await api_client.get(
        "/audit/logs?limit=100&offset=0",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(logs_response, 200)
    logs = logs_response.json()["items"]
    matched = [
        item
        for item in logs
        if item["action"] == "admin.slot.block" and item["entity_id"] == slot_id
    ]
    assert matched
    assert matched[0]["payload"]["reason"] == "Teacher unavailable"


@pytest.mark.asyncio
async def test_teacher_profile_create_forbidden_for_student_and_update_allowed_for_teacher(
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
    _assert_status(teacher_response, 409)

    profiles_response = await api_client.get(
        "/teachers/profiles?limit=20&offset=0",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(profiles_response, 200)
    teacher_profile = next(
        item
        for item in profiles_response.json()["items"]
        if item["user_id"] == str(teacher.id)
    )

    update_response = await api_client.patch(
        f"/teachers/profiles/{teacher_profile['id']}",
        headers=_auth_headers(teacher.access_token),
        json={
            "display_name": "Teacher Self Profile",
            "bio": "test",
            "experience_years": 5,
        },
    )
    _assert_status(update_response, 200)
    updated = update_response.json()
    assert updated["user_id"] == str(teacher.id)
    assert updated["display_name"] == "Teacher Self Profile"


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
