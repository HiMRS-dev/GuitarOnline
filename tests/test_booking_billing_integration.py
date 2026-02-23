"""HTTP + DB integration tests for booking and billing business rules."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio

from app.core.security import create_access_token

API_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
HEALTHCHECK_URL = os.getenv("INTEGRATION_HEALTH_URL", "http://localhost:8000/health")
DB_DSN = os.getenv("INTEGRATION_DB_DSN", "postgresql://postgres:postgres@localhost:5432/guitaronline")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))


@dataclass(slots=True)
class AuthUser:
    id: UUID
    access_token: str


def _assert_status(response: httpx.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"{response.request.method} {response.request.url} -> "
        f"{response.status_code}, body={response.text}"
    )


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _future_range(hours_from_now: int, duration_minutes: int = 60) -> tuple[str, str]:
    start_at = datetime.now(UTC) + timedelta(hours=hours_from_now)
    end_at = start_at + timedelta(minutes=duration_minutes)
    return start_at.isoformat(), end_at.isoformat()


async def _register_and_login(client: httpx.AsyncClient, role: str) -> AuthUser:
    try:
        connection = await asyncpg.connect(DB_DSN)
    except Exception as exc:
        pytest.skip(f"PostgreSQL is unavailable for integration user setup: {exc}")
        return AuthUser(id=uuid4(), access_token="")

    try:
        role_id = await connection.fetchval("SELECT id FROM roles WHERE name = $1", role.upper())
        if role_id is None:
            raise AssertionError(f"Role '{role}' not found in DB")

        user_id = uuid4()
        now = datetime.now(UTC)
        email = f"{role}-{uuid4().hex}@guitaronline.dev"
        await connection.execute(
            "INSERT INTO users "
            "(id, created_at, updated_at, email, password_hash, timezone, is_active, role_id) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            user_id,
            now,
            now,
            email,
            "integration-not-used",
            "UTC",
            True,
            role_id,
        )
    finally:
        await connection.close()

    access_token = create_access_token(subject=str(user_id), role=role)
    return AuthUser(id=user_id, access_token=access_token)


async def _create_package(
    client: httpx.AsyncClient,
    admin: AuthUser,
    student: AuthUser,
    lessons_total: int,
) -> dict:
    response = await client.post(
        "/billing/packages",
        headers=_auth_headers(admin.access_token),
        json={
            "student_id": str(student.id),
            "lessons_total": lessons_total,
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    _assert_status(response, 201)
    return response.json()


async def _get_package_for_student(
    client: httpx.AsyncClient,
    student: AuthUser,
    package_id: str,
) -> dict:
    response = await client.get(
        f"/billing/packages/students/{student.id}",
        headers=_auth_headers(student.access_token),
        params={"limit": 100, "offset": 0},
    )
    _assert_status(response, 200)
    items = response.json()["items"]
    for package in items:
        if package["id"] == package_id:
            return package
    raise AssertionError(f"Package {package_id} not found for student {student.id}")


async def _create_slot(
    client: httpx.AsyncClient,
    admin: AuthUser,
    teacher: AuthUser,
    *,
    hours_from_now: int,
) -> dict:
    start_at, end_at = _future_range(hours_from_now)
    response = await client.post(
        "/scheduling/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at": start_at,
            "end_at": end_at,
        },
    )
    _assert_status(response, 201)
    return response.json()


async def _hold_and_confirm_booking(
    client: httpx.AsyncClient,
    student: AuthUser,
    *,
    slot_id: str,
    package_id: str,
) -> tuple[dict, dict]:
    hold_response = await client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot_id, "package_id": package_id},
    )
    _assert_status(hold_response, 200)
    hold_booking = hold_response.json()

    confirm_response = await client.post(
        f"/booking/{hold_booking['id']}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(confirm_response, 200)
    return hold_booking, confirm_response.json()


async def _list_my_bookings(client: httpx.AsyncClient, user: AuthUser) -> list[dict]:
    response = await client.get(
        "/booking/my",
        headers=_auth_headers(user.access_token),
        params={"limit": 100, "offset": 0},
    )
    _assert_status(response, 200)
    return response.json()["items"]


def _find_booking(bookings: list[dict], booking_id: str) -> dict:
    for booking in bookings:
        if booking["id"] == booking_id:
            return booking
    raise AssertionError(f"Booking {booking_id} not found")


async def _open_slot_ids(client: httpx.AsyncClient, teacher_id: UUID) -> set[str]:
    response = await client.get(
        "/scheduling/slots/open",
        params={"teacher_id": str(teacher_id), "limit": 100, "offset": 0},
    )
    _assert_status(response, 200)
    return {slot["id"] for slot in response.json()["items"]}


async def _force_hold_expired(booking_id: UUID) -> None:
    try:
        connection = await asyncpg.connect(DB_DSN)
    except Exception as exc:
        pytest.skip(f"PostgreSQL is unavailable for hold expiration scenario: {exc}")
        return

    try:
        result = await connection.execute(
            "UPDATE bookings "
            "SET hold_expires_at = NOW() - INTERVAL '2 minutes' "
            "WHERE id = $1",
            booking_id,
        )
    finally:
        await connection.close()

    assert result == "UPDATE 1", f"Expected exactly one booking updated, got: {result}"


@pytest_asyncio.fixture()
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as probe:
        try:
            health_response = await probe.get(HEALTHCHECK_URL)
        except httpx.HTTPError as exc:
            pytest.skip(f"Integration stack unavailable at {HEALTHCHECK_URL}: {exc}")
            return
        if health_response.status_code != 200:
            pytest.skip(
                f"Integration stack returned {health_response.status_code} "
                f"for {HEALTHCHECK_URL}",
            )
            return

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        yield client


@pytest.mark.asyncio
async def test_student_hold_confirm_decrements_package_lessons(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, role="admin")
    teacher = await _register_and_login(api_client, role="teacher")
    student = await _register_and_login(api_client, role="student")

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=48)

    _, confirmed_booking = await _hold_and_confirm_booking(
        api_client,
        student,
        slot_id=slot["id"],
        package_id=package["id"],
    )
    package_after_confirm = await _get_package_for_student(api_client, student, package["id"])

    assert confirmed_booking["status"] == "confirmed"
    assert package_after_confirm["lessons_left"] == 4


@pytest.mark.asyncio
async def test_cancel_more_than_24h_returns_lesson(api_client: httpx.AsyncClient) -> None:
    admin = await _register_and_login(api_client, role="admin")
    teacher = await _register_and_login(api_client, role="teacher")
    student = await _register_and_login(api_client, role="student")

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=30)
    _, confirmed_booking = await _hold_and_confirm_booking(
        api_client,
        student,
        slot_id=slot["id"],
        package_id=package["id"],
    )

    cancel_response = await api_client.post(
        f"/booking/{confirmed_booking['id']}/cancel",
        headers=_auth_headers(student.access_token),
        json={"reason": "Integration cancel >24h"},
    )
    _assert_status(cancel_response, 200)
    canceled_booking = cancel_response.json()
    package_after_cancel = await _get_package_for_student(api_client, student, package["id"])

    assert canceled_booking["status"] == "canceled"
    assert canceled_booking["refund_returned"] is True
    assert package_after_cancel["lessons_left"] == 5


@pytest.mark.asyncio
async def test_cancel_less_than_24h_does_not_return_lesson(api_client: httpx.AsyncClient) -> None:
    admin = await _register_and_login(api_client, role="admin")
    teacher = await _register_and_login(api_client, role="teacher")
    student = await _register_and_login(api_client, role="student")

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=12)
    _, confirmed_booking = await _hold_and_confirm_booking(
        api_client,
        student,
        slot_id=slot["id"],
        package_id=package["id"],
    )

    cancel_response = await api_client.post(
        f"/booking/{confirmed_booking['id']}/cancel",
        headers=_auth_headers(student.access_token),
        json={"reason": "Integration cancel <24h"},
    )
    _assert_status(cancel_response, 200)
    canceled_booking = cancel_response.json()
    package_after_cancel = await _get_package_for_student(api_client, student, package["id"])

    assert canceled_booking["status"] == "canceled"
    assert canceled_booking["refund_returned"] is False
    assert package_after_cancel["lessons_left"] == 4


@pytest.mark.asyncio
async def test_reschedule_keeps_balance_and_links_bookings(api_client: httpx.AsyncClient) -> None:
    admin = await _register_and_login(api_client, role="admin")
    teacher = await _register_and_login(api_client, role="teacher")
    student = await _register_and_login(api_client, role="student")

    package = await _create_package(api_client, admin, student, lessons_total=5)
    old_slot = await _create_slot(api_client, admin, teacher, hours_from_now=48)
    new_slot = await _create_slot(api_client, admin, teacher, hours_from_now=72)
    _, old_confirmed_booking = await _hold_and_confirm_booking(
        api_client,
        student,
        slot_id=old_slot["id"],
        package_id=package["id"],
    )

    reschedule_response = await api_client.post(
        f"/booking/{old_confirmed_booking['id']}/reschedule",
        headers=_auth_headers(student.access_token),
        json={"new_slot_id": new_slot["id"]},
    )
    _assert_status(reschedule_response, 200)
    new_booking = reschedule_response.json()

    package_after_reschedule = await _get_package_for_student(api_client, student, package["id"])
    open_slot_ids = await _open_slot_ids(api_client, teacher.id)
    student_bookings = await _list_my_bookings(api_client, student)
    old_booking_after_reschedule = _find_booking(student_bookings, old_confirmed_booking["id"])

    assert new_booking["status"] == "confirmed"
    assert new_booking["rescheduled_from_booking_id"] == old_confirmed_booking["id"]
    assert old_booking_after_reschedule["status"] == "canceled"
    assert package_after_reschedule["lessons_left"] == 4
    assert old_slot["id"] in open_slot_ids
    assert new_slot["id"] not in open_slot_ids


@pytest.mark.asyncio
async def test_expire_holds_releases_slot_and_marks_booking_expired(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, role="admin")
    teacher = await _register_and_login(api_client, role="teacher")
    student = await _register_and_login(api_client, role="student")

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=48)

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot["id"], "package_id": package["id"]},
    )
    _assert_status(hold_response, 200)
    held_booking = hold_response.json()

    await _force_hold_expired(UUID(held_booking["id"]))

    expire_response = await api_client.post(
        "/booking/holds/expire",
        headers=_auth_headers(admin.access_token),
    )
    _assert_status(expire_response, 200)
    expired_count = expire_response.json()

    student_bookings = await _list_my_bookings(api_client, student)
    expired_booking = _find_booking(student_bookings, held_booking["id"])
    open_slot_ids = await _open_slot_ids(api_client, teacher.id)

    assert expired_count >= 1
    assert expired_booking["status"] == "expired"
    assert slot["id"] in open_slot_ids
