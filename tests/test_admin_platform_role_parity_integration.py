"""Integration parity checks for admin/teacher/student role flows."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio

from tests.integration_smoke_pool import AuthUser, login_smoke_auth_user, reset_test_smoke_pool

API_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:18000/api/v1").rstrip("/")
HEALTHCHECK_URL = os.getenv("INTEGRATION_HEALTH_URL", "http://localhost:18000/health")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))

_INTEGRATION_STACK_HEALTHY: bool | None = None
_INTEGRATION_STACK_ERROR: str | None = None


def _assert_status(response: httpx.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"{response.request.method} {response.request.url} -> "
        f"{response.status_code}, body={response.text}"
    )


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_login(client: httpx.AsyncClient, role: str) -> AuthUser:
    return await login_smoke_auth_user(client, role=role)


def _target_weekday_for_teacher_timezone(timezone_name: str) -> int:
    teacher_zone = ZoneInfo(timezone_name)
    now_local = datetime.now(UTC).astimezone(teacher_zone)
    return (now_local.weekday() + 1) % 7


@pytest_asyncio.fixture()
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    global _INTEGRATION_STACK_HEALTHY, _INTEGRATION_STACK_ERROR  # noqa: PLW0603

    if _INTEGRATION_STACK_HEALTHY is None:
        probe_timeout_seconds = min(REQUEST_TIMEOUT_SECONDS, 3.0)
        async with httpx.AsyncClient(timeout=probe_timeout_seconds, trust_env=False) as probe:
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

    async with httpx.AsyncClient(
        base_url=API_BASE_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        trust_env=False,
    ) as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def smoke_pool_reset(api_client: httpx.AsyncClient) -> AsyncIterator[None]:
    reset_test_smoke_pool()
    yield


@pytest.mark.asyncio
async def test_schedule_generation_and_open_slots_parity_by_role(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    teacher = await _register_and_login(api_client, "teacher")
    student = await _register_and_login(api_client, "student")

    admin_teacher_detail = await api_client.get(
        f"/admin/teachers/{teacher.id}",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(admin_teacher_detail, 200)
    teacher_timezone = str(admin_teacher_detail.json().get("timezone", "UTC"))
    target_weekday = _target_weekday_for_teacher_timezone(teacher_timezone)

    teacher_admin_schedule_attempt = await api_client.get(
        f"/admin/teachers/{teacher.id}/schedule",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_admin_schedule_attempt, 403)

    student_admin_schedule_attempt = await api_client.get(
        f"/admin/teachers/{teacher.id}/schedule",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_admin_schedule_attempt, 403)

    replace_schedule_response = await api_client.put(
        f"/admin/teachers/{teacher.id}/schedule",
        headers=_auth_headers(admin.access_token),
        json={
            "windows": [
                {
                    "weekday": target_weekday,
                    "start_local_time": "10:00:00",
                    "end_local_time": "11:00:00",
                }
            ]
        },
    )
    _assert_status(replace_schedule_response, 200)
    replaced_payload = replace_schedule_response.json()
    assert replaced_payload["teacher_id"] == str(teacher.id)
    assert replaced_payload["timezone"] == teacher_timezone
    assert len(replaced_payload["windows"]) == 1
    assert replaced_payload["windows"][0]["weekday"] == target_weekday

    teacher_schedule_response = await api_client.get(
        "/scheduling/teachers/me/schedule",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(teacher_schedule_response, 200)
    teacher_schedule = teacher_schedule_response.json()
    assert teacher_schedule["teacher_id"] == str(teacher.id)
    assert len(teacher_schedule["windows"]) == 1

    student_teacher_schedule_response = await api_client.get(
        "/scheduling/teachers/me/schedule",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(student_teacher_schedule_response, 403)

    admin_slots_response = await api_client.get(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        params={"teacher_id": str(teacher.id), "limit": 50, "offset": 0},
    )
    _assert_status(admin_slots_response, 200)
    admin_slot_items = admin_slots_response.json().get("items", [])
    generated_admin_open_slot_ids = {
        str(item.get("slot_id"))
        for item in admin_slot_items
        if item.get("slot_status") == "open"
    }
    assert generated_admin_open_slot_ids

    teacher_open_slots_response = await api_client.get(
        "/scheduling/slots/open",
        headers=_auth_headers(teacher.access_token),
        params={"teacher_id": str(teacher.id), "limit": 50, "offset": 0},
    )
    _assert_status(teacher_open_slots_response, 200)
    teacher_open_slot_ids = {
        str(item.get("id")) for item in teacher_open_slots_response.json().get("items", [])
    }
    assert generated_admin_open_slot_ids.issubset(teacher_open_slot_ids)

    student_open_slots_response = await api_client.get(
        "/scheduling/slots/open",
        headers=_auth_headers(student.access_token),
        params={"teacher_id": str(teacher.id), "limit": 50, "offset": 0},
    )
    _assert_status(student_open_slots_response, 200)
    student_open_slot_ids = {
        str(item.get("id")) for item in student_open_slots_response.json().get("items", [])
    }
    assert generated_admin_open_slot_ids.issubset(student_open_slot_ids)
