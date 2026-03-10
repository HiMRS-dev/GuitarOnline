"""HTTP + DB integration tests for booking and billing business rules."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio

API_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
HEALTHCHECK_URL = os.getenv("INTEGRATION_HEALTH_URL", "http://localhost:8000/health")
DB_DSN = os.getenv("INTEGRATION_DB_DSN", "postgresql://postgres:postgres@localhost:5432/guitaronline")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))


@dataclass(slots=True)
class AuthUser:
    id: UUID
    access_token: str


@dataclass(slots=True)
class AuthUsers:
    admin: AuthUser
    teacher: AuthUser
    student: AuthUser


_CACHED_AUTH_USERS: AuthUsers | None = None
_INTEGRATION_STACK_HEALTHY: bool | None = None
_INTEGRATION_STACK_ERROR: str | None = None
_SLOT_WINDOWS: list[tuple[datetime, datetime]] = []


def _assert_status(response: httpx.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"{response.request.method} {response.request.url} -> "
        f"{response.status_code}, body={response.text}"
    )


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _future_range(hours_from_now: int, duration_minutes: int = 60) -> tuple[str, str]:
    start_at = datetime.now(UTC) + timedelta(hours=hours_from_now)
    duration = timedelta(minutes=duration_minutes)
    end_at = start_at + duration

    while any(
        start_at < existing_end and existing_start < end_at
        for existing_start, existing_end in _SLOT_WINDOWS
    ):
        start_at += timedelta(minutes=65)
        end_at = start_at + duration

    _SLOT_WINDOWS.append((start_at, end_at))
    return start_at.isoformat(), end_at.isoformat()


async def _register_and_login(client: httpx.AsyncClient, role: str) -> AuthUser:
    email = f"{role}-{uuid4().hex}@guitaronline.dev"
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


async def _list_teacher_lessons(client: httpx.AsyncClient, teacher: AuthUser) -> list[dict]:
    response = await client.get(
        "/teacher/lessons",
        headers=_auth_headers(teacher.access_token),
        params={"limit": 100, "offset": 0},
    )
    _assert_status(response, 200)
    return response.json()["items"]


async def _find_lesson_id_by_booking(
    client: httpx.AsyncClient,
    teacher: AuthUser,
    booking_id: str,
) -> str:
    for lesson in await _list_teacher_lessons(client, teacher):
        if lesson.get("booking_id") == booking_id:
            return str(lesson["id"])
    raise AssertionError(f"Lesson for booking {booking_id} not found")


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


async def _count_active_bookings_for_slot(slot_id: UUID) -> int:
    try:
        connection = await asyncpg.connect(DB_DSN)
    except Exception as exc:
        pytest.skip(f"PostgreSQL is unavailable for hold concurrency scenario: {exc}")
        return 0

    try:
        value = await connection.fetchval(
            """
            SELECT COUNT(*)::int
            FROM bookings
            WHERE slot_id = $1
              AND LOWER(status::text) IN ('hold', 'confirmed')
            """,
            slot_id,
        )
    finally:
        await connection.close()

    return int(value or 0)


@pytest_asyncio.fixture()
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    global _INTEGRATION_STACK_HEALTHY, _INTEGRATION_STACK_ERROR  # noqa: PLW0603 - cached probe state

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


@pytest_asyncio.fixture()
async def auth_users(api_client: httpx.AsyncClient) -> AuthUsers:
    global _CACHED_AUTH_USERS  # noqa: PLW0603 - intentional cache for rate-limit-safe integration setup

    if _CACHED_AUTH_USERS is None:
        _CACHED_AUTH_USERS = AuthUsers(
            admin=await _register_and_login(api_client, role="admin"),
            teacher=await _register_and_login(api_client, role="teacher"),
            student=await _register_and_login(api_client, role="student"),
        )

    return _CACHED_AUTH_USERS


@pytest.mark.asyncio
async def test_student_hold_confirm_reserves_package_capacity(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

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
    assert package_after_confirm["lessons_left"] == 5
    assert package_after_confirm["lessons_reserved"] == 1


@pytest.mark.asyncio
async def test_confirm_creates_single_lesson_and_repeat_confirm_is_idempotent(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=60)

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot["id"], "package_id": package["id"]},
    )
    _assert_status(hold_response, 200)
    hold_booking = hold_response.json()
    booking_id = hold_booking["id"]

    first_confirm_response = await api_client.post(
        f"/booking/{booking_id}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(first_confirm_response, 200)
    first_confirmed_booking = first_confirm_response.json()

    second_confirm_response = await api_client.post(
        f"/booking/{booking_id}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(second_confirm_response, 200)
    second_confirmed_booking = second_confirm_response.json()

    package_after_second_confirm = await _get_package_for_student(
        api_client,
        student,
        package["id"],
    )
    teacher_lessons = await _list_teacher_lessons(api_client, teacher)
    lessons_for_booking = [
        lesson for lesson in teacher_lessons if lesson.get("booking_id") == booking_id
    ]

    assert first_confirmed_booking["status"] == "confirmed"
    assert second_confirmed_booking["status"] == "confirmed"
    assert first_confirmed_booking["id"] == booking_id
    assert second_confirmed_booking["id"] == booking_id
    assert package_after_second_confirm["lessons_left"] == 5
    assert package_after_second_confirm["lessons_reserved"] == 1
    assert len(lessons_for_booking) == 1
    assert lessons_for_booking[0]["booking_id"] == booking_id
    assert lessons_for_booking[0]["teacher_id"] == str(teacher.id)
    assert lessons_for_booking[0]["student_id"] == str(student.id)


@pytest.mark.asyncio
async def test_cancel_more_than_24h_returns_lesson(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

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
    assert package_after_cancel["lessons_reserved"] == 0


@pytest.mark.asyncio
async def test_cancel_less_than_24h_does_not_return_lesson(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

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
    assert package_after_cancel["lessons_reserved"] == 0


@pytest.mark.asyncio
async def test_rebook_same_slot_after_cancel_succeeds_with_active_booking_uniqueness(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=30)
    _, first_confirmed_booking = await _hold_and_confirm_booking(
        api_client,
        student,
        slot_id=slot["id"],
        package_id=package["id"],
    )

    first_cancel_response = await api_client.post(
        f"/booking/{first_confirmed_booking['id']}/cancel",
        headers=_auth_headers(student.access_token),
        json={"reason": "Rebook same slot"},
    )
    _assert_status(first_cancel_response, 200)
    first_canceled_booking = first_cancel_response.json()
    assert first_canceled_booking["status"] == "canceled"

    second_hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot["id"], "package_id": package["id"]},
    )
    _assert_status(second_hold_response, 200)
    second_hold_booking = second_hold_response.json()

    second_confirm_response = await api_client.post(
        f"/booking/{second_hold_booking['id']}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(second_confirm_response, 200)
    second_confirmed_booking = second_confirm_response.json()

    package_after_rebook = await _get_package_for_student(api_client, student, package["id"])
    student_bookings = await _list_my_bookings(api_client, student)
    first_booking_after_rebook = _find_booking(student_bookings, first_confirmed_booking["id"])
    second_booking_after_rebook = _find_booking(student_bookings, second_confirmed_booking["id"])
    active_booking_count = await _count_active_bookings_for_slot(UUID(slot["id"]))

    assert first_booking_after_rebook["status"] == "canceled"
    assert second_booking_after_rebook["status"] == "confirmed"
    assert second_booking_after_rebook["slot_id"] == slot["id"]
    assert package_after_rebook["lessons_left"] == 5
    assert package_after_rebook["lessons_reserved"] == 1
    assert active_booking_count == 1


@pytest.mark.asyncio
async def test_reschedule_keeps_balance_and_links_bookings(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

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
    assert package_after_reschedule["lessons_left"] == 5
    assert package_after_reschedule["lessons_reserved"] == 1
    assert old_slot["id"] in open_slot_ids
    assert new_slot["id"] not in open_slot_ids


@pytest.mark.asyncio
async def test_confirm_reserves_and_complete_consumes_package_capacity(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=48)
    _, confirmed_booking = await _hold_and_confirm_booking(
        api_client,
        student,
        slot_id=slot["id"],
        package_id=package["id"],
    )

    package_after_confirm = await _get_package_for_student(api_client, student, package["id"])
    assert package_after_confirm["lessons_left"] == 5
    assert package_after_confirm["lessons_reserved"] == 1

    lesson_id = await _find_lesson_id_by_booking(
        api_client,
        teacher,
        booking_id=confirmed_booking["id"],
    )
    complete_response = await api_client.post(
        f"/lessons/{lesson_id}/complete",
        headers=_auth_headers(teacher.access_token),
    )
    _assert_status(complete_response, 200)
    completed_lesson = complete_response.json()
    package_after_complete = await _get_package_for_student(api_client, student, package["id"])

    assert completed_lesson["status"] == "completed"
    assert completed_lesson["consumed_at"] is not None
    assert package_after_complete["lessons_left"] == 4
    assert package_after_complete["lessons_reserved"] == 0


@pytest.mark.asyncio
async def test_expire_holds_releases_slot_and_marks_booking_expired(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

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


@pytest.mark.asyncio
async def test_concurrent_hold_attempts_on_same_slot_allow_only_one_success(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student_one = auth_users.student
    student_two = await _register_and_login(api_client, role="student")

    package_one = await _create_package(api_client, admin, student_one, lessons_total=5)
    package_two = await _create_package(api_client, admin, student_two, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=54)

    async def hold(student: AuthUser, package_id: str) -> httpx.Response:
        return await api_client.post(
            "/booking/hold",
            headers=_auth_headers(student.access_token),
            json={"slot_id": slot["id"], "package_id": package_id},
        )

    response_one, response_two = await asyncio.gather(
        hold(student_one, package_one["id"]),
        hold(student_two, package_two["id"]),
    )
    statuses = sorted([response_one.status_code, response_two.status_code])
    assert statuses == [200, 422]

    failed_response = response_one if response_one.status_code != 200 else response_two
    failed_body = failed_response.json()
    assert failed_body["error"]["code"] == "business_rule_violation"
    assert "Slot is not available" in failed_body["error"]["message"]

    active_booking_count = await _count_active_bookings_for_slot(UUID(slot["id"]))
    assert active_booking_count == 1


@pytest.mark.asyncio
async def test_concurrent_confirm_on_two_slots_with_last_package_lesson_allows_only_one_success(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

    package = await _create_package(api_client, admin, student, lessons_total=1)
    first_slot = await _create_slot(api_client, admin, teacher, hours_from_now=66)
    second_slot = await _create_slot(api_client, admin, teacher, hours_from_now=78)

    first_hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": first_slot["id"], "package_id": package["id"]},
    )
    _assert_status(first_hold_response, 200)
    first_hold = first_hold_response.json()

    second_hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": second_slot["id"], "package_id": package["id"]},
    )
    _assert_status(second_hold_response, 200)
    second_hold = second_hold_response.json()

    async def confirm(booking_id: str) -> httpx.Response:
        return await api_client.post(
            f"/booking/{booking_id}/confirm",
            headers=_auth_headers(student.access_token),
        )

    first_confirm_response, second_confirm_response = await asyncio.gather(
        confirm(first_hold["id"]),
        confirm(second_hold["id"]),
    )

    statuses = sorted([first_confirm_response.status_code, second_confirm_response.status_code])
    assert statuses == [200, 422]

    failed_response = (
        first_confirm_response
        if first_confirm_response.status_code != 200
        else second_confirm_response
    )
    failed_body = failed_response.json()
    assert failed_body["error"]["code"] == "business_rule_violation"
    assert "No lessons left" in failed_body["error"]["message"]

    package_after = await _get_package_for_student(api_client, student, package["id"])
    assert package_after["lessons_left"] == 1
    assert package_after["lessons_reserved"] == 1

    student_bookings = await _list_my_bookings(api_client, student)
    booking_statuses = {
        booking["id"]: booking["status"]
        for booking in student_bookings
        if booking["id"] in {first_hold["id"], second_hold["id"]}
    }
    assert sorted(booking_statuses.values()) == ["confirmed", "hold"]


@pytest.mark.asyncio
async def test_confirm_rejects_hold_when_slot_start_already_passed(
    api_client: httpx.AsyncClient,
    auth_users: AuthUsers,
) -> None:
    admin = auth_users.admin
    teacher = auth_users.teacher
    student = auth_users.student

    package = await _create_package(api_client, admin, student, lessons_total=5)
    slot = await _create_slot(api_client, admin, teacher, hours_from_now=30)

    hold_response = await api_client.post(
        "/booking/hold",
        headers=_auth_headers(student.access_token),
        json={"slot_id": slot["id"], "package_id": package["id"]},
    )
    _assert_status(hold_response, 200)
    held_booking = hold_response.json()

    try:
        connection = await asyncpg.connect(DB_DSN)
    except Exception as exc:
        pytest.skip(f"PostgreSQL is unavailable for past-confirm scenario: {exc}")
        return

    try:
        booking_update = await connection.execute(
            """
            UPDATE bookings
            SET hold_expires_at = NOW() + INTERVAL '5 minutes'
            WHERE id = $1
            """,
            UUID(held_booking["id"]),
        )
        slot_update = await connection.execute(
            """
            UPDATE availability_slots
            SET start_at = NOW() - INTERVAL '1 minute',
                end_at = NOW() + INTERVAL '59 minutes'
            WHERE id = $1
            """,
            UUID(slot["id"]),
        )
    finally:
        await connection.close()

    assert booking_update == "UPDATE 1"
    assert slot_update == "UPDATE 1"

    confirm_response = await api_client.post(
        f"/booking/{held_booking['id']}/confirm",
        headers=_auth_headers(student.access_token),
    )
    _assert_status(confirm_response, 422)
    body = confirm_response.json()
    assert body["error"]["code"] == "business_rule_violation"
    assert "Cannot confirm booking for slot in the past" in body["error"]["message"]
