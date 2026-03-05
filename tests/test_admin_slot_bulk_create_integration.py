"""Integration scenario for admin bulk-create overlap guarantees."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio

API_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
HEALTHCHECK_URL = os.getenv("INTEGRATION_HEALTH_URL", "http://localhost:8000/health")
DB_DSN = os.getenv("INTEGRATION_DB_DSN", "postgresql://postgres:postgres@localhost:5432/guitaronline")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "15"))

_INTEGRATION_STACK_HEALTHY: bool | None = None
_INTEGRATION_STACK_ERROR: str | None = None


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


async def _register_and_login(client: httpx.AsyncClient, role: str) -> AuthUser:
    email = f"bulk-overlap-{role}-{uuid4().hex}@guitaronline.dev"
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


async def _count_teacher_overlaps(
    teacher_id: UUID,
    *,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> int:
    try:
        connection = await asyncpg.connect(DB_DSN)
    except Exception as exc:
        pytest.skip(f"PostgreSQL is unavailable for overlap integration scenario: {exc}")
        return 0

    try:
        count = await connection.fetchval(
            """
            SELECT COUNT(*)::int
            FROM availability_slots s1
            JOIN availability_slots s2
              ON s1.teacher_id = s2.teacher_id
             AND s1.id < s2.id
             AND s1.start_at < s2.end_at
             AND s1.end_at > s2.start_at
            WHERE s1.teacher_id = $1
              AND s1.start_at < $3
              AND s1.end_at > $2
              AND s2.start_at < $3
              AND s2.end_at > $2
            """,
            teacher_id,
            window_start_utc,
            window_end_utc,
        )
    finally:
        await connection.close()

    return int(count or 0)


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
async def test_admin_bulk_create_keeps_teacher_slots_non_overlapping_in_db(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await _register_and_login(api_client, "admin")
    teacher = await _register_and_login(api_client, "teacher")

    target_day: date = (datetime.now(UTC) + timedelta(days=14)).date()
    seed_start = datetime.combine(target_day, time(10, 0), tzinfo=UTC)
    seed_end = seed_start + timedelta(minutes=30)

    seed_slot_response = await api_client.post(
        "/admin/slots",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "start_at_utc": seed_start.isoformat(),
            "end_at_utc": seed_end.isoformat(),
        },
    )
    _assert_status(seed_slot_response, 201)

    bulk_create_response = await api_client.post(
        "/admin/slots/bulk-create",
        headers=_auth_headers(admin.access_token),
        json={
            "teacher_id": str(teacher.id),
            "date_from_utc": target_day.isoformat(),
            "date_to_utc": target_day.isoformat(),
            "weekdays": [target_day.weekday()],
            "start_time_utc": "10:00:00",
            "end_time_utc": "12:00:00",
            "slot_duration_minutes": 30,
        },
    )
    _assert_status(bulk_create_response, 200)
    payload = bulk_create_response.json()
    assert payload["created_count"] >= 1
    assert payload["skipped_count"] >= 1
    assert any(
        "overlaps with an existing slot" in item["reason"]
        for item in payload["skipped"]
    )

    overlaps = await _count_teacher_overlaps(
        teacher.id,
        window_start_utc=datetime.combine(target_day, time(0, 0), tzinfo=UTC),
        window_end_utc=datetime.combine(target_day + timedelta(days=1), time(0, 0), tzinfo=UTC),
    )
    assert overlaps == 0
