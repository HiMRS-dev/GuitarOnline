"""Post-deploy smoke checks executed from the app container."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
import urllib.error
import urllib.request
from urllib.parse import urlencode
from uuid import uuid4

BASE_URL = "http://localhost:8000"


def request(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    expected: int = 200,
) -> bytes:
    payload = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    request_obj = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=payload,
        method=method,
        headers=req_headers,
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            content = response.read()
            status = response.getcode()
    except urllib.error.HTTPError as exc:  # pragma: no cover - runtime smoke script
        body_text = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {body_text}") from exc

    if status != expected:
        raise RuntimeError(f"{method} {path} -> {status}, expected {expected}")
    return content


def request_json(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    expected: int = 200,
) -> dict[str, object]:
    """Perform request and parse JSON response body."""
    raw = request(path, method=method, body=body, headers=headers, expected=expected)
    return json.loads(raw.decode("utf-8"))


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def main() -> None:
    for endpoint in [
        "/health",
        "/ready",
        "/docs",
        "/metrics",
        "/portal",
        "/portal/static/app.js",
        "/portal/static/styles.css",
    ]:
        request(endpoint, expected=200)

    suffix = uuid4().hex[:10]
    password = "StrongPass123!"

    admin_email = f"deploy-smoke-admin-{suffix}@guitaronline.dev"
    teacher_email = f"deploy-smoke-teacher-{suffix}@guitaronline.dev"
    student_email = f"deploy-smoke-student-{suffix}@guitaronline.dev"

    request_json(
        "/api/v1/identity/auth/register",
        method="POST",
        body={
            "email": admin_email,
            "password": password,
            "timezone": "UTC",
            "role": "admin",
        },
        expected=201,
    )
    teacher_user = request_json(
        "/api/v1/identity/auth/register",
        method="POST",
        body={
            "email": teacher_email,
            "password": password,
            "timezone": "UTC",
            "role": "teacher",
        },
        expected=201,
    )
    student_user = request_json(
        "/api/v1/identity/auth/register",
        method="POST",
        body={
            "email": student_email,
            "password": password,
            "timezone": "UTC",
            "role": "student",
        },
        expected=201,
    )

    admin_login = request_json(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": admin_email, "password": password},
        expected=200,
    )
    teacher_login = request_json(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": teacher_email, "password": password},
        expected=200,
    )
    student_login = request_json(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": student_email, "password": password},
        expected=200,
    )

    request(
        "/api/v1/identity/users/me",
        headers=auth_headers(str(student_login["access_token"])),
        expected=200,
    )

    request_json(
        "/api/v1/teachers/profiles",
        method="POST",
        headers=auth_headers(str(teacher_login["access_token"])),
        body={
            "user_id": str(teacher_user["id"]),
            "display_name": "Deploy Smoke Teacher",
            "bio": "Smoke test profile",
            "experience_years": 3,
        },
        expected=201,
    )

    teacher_query = urlencode(
        {"q": "Deploy Smoke Teacher", "limit": 5, "offset": 0},
    )
    teachers_page = request_json(
        f"/api/v1/admin/teachers?{teacher_query}",
        headers=auth_headers(str(admin_login["access_token"])),
        expected=200,
    )
    if int(teachers_page.get("total", 0)) < 1:
        raise RuntimeError("Admin teachers list returned no teachers")

    now = datetime.now(UTC)
    slot_start = (now + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    slot_end = slot_start + timedelta(minutes=30)
    created_slot = request_json(
        "/api/v1/admin/slots",
        method="POST",
        headers=auth_headers(str(admin_login["access_token"])),
        body={
            "teacher_id": str(teacher_user["id"]),
            "start_at_utc": slot_start.isoformat(),
            "end_at_utc": slot_end.isoformat(),
        },
        expected=201,
    )

    created_package = request_json(
        "/api/v1/admin/packages",
        method="POST",
        headers=auth_headers(str(admin_login["access_token"])),
        body={
            "student_id": str(student_user["id"]),
            "lessons_total": 2,
            "expires_at_utc": (now + timedelta(days=30)).isoformat(),
            "price_amount": "120.00",
            "price_currency": "USD",
        },
        expected=201,
    )

    hold_booking = request_json(
        "/api/v1/booking/hold",
        method="POST",
        headers=auth_headers(str(student_login["access_token"])),
        body={
            "slot_id": str(created_slot["slot_id"]),
            "package_id": str(created_package["package_id"]),
        },
        expected=200,
    )
    confirmed_booking = request_json(
        f"/api/v1/booking/{hold_booking['id']}/confirm",
        method="POST",
        headers=auth_headers(str(student_login["access_token"])),
        expected=200,
    )
    if confirmed_booking.get("status") != "confirmed":
        raise RuntimeError("Booking confirm smoke check failed")

    print("Smoke checks passed.")


if __name__ == "__main__":
    main()
