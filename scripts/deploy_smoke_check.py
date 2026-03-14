"""Post-deploy smoke checks executed from the app container."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

BASE_URL = os.getenv("DEPLOY_SMOKE_BASE_URL", "http://localhost:8000").rstrip("/")


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


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def extract_page_items(payload: dict[str, object], endpoint: str) -> list[dict[str, object]]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError(f"{endpoint} did not return paginated items list")
    return [item for item in items if isinstance(item, dict)]


def main() -> None:
    print("Smoke: health/readiness/static checks")
    for endpoint in [
        "/health",
        "/ready",
        "/docs",
        "/metrics",
        "/portal",
        "/admin/",
        "/portal/static/app.js",
        "/portal/static/styles.css",
    ]:
        request(endpoint, expected=200)

    suffix = uuid4().hex[:10]
    shared_credential = "StrongPass123!"
    now_utc = datetime.now(UTC)

    configured_admin_email = os.getenv("DEPLOY_SMOKE_ADMIN_EMAIL", "").strip()
    configured_admin_password = os.getenv("DEPLOY_SMOKE_ADMIN_PASSWORD", "")

    teacher_email = f"deploy-smoke-teacher-{suffix}@guitaronline.dev"
    student_email = f"deploy-smoke-student-{suffix}@guitaronline.dev"
    if not configured_admin_email or not configured_admin_password:
        raise RuntimeError(
            "Set DEPLOY_SMOKE_ADMIN_EMAIL and DEPLOY_SMOKE_ADMIN_PASSWORD. "
            "Public registration no longer creates admin accounts."
        )

    print("Smoke: admin login with configured credentials")
    admin_email = configured_admin_email
    admin_password = configured_admin_password

    print("Smoke: student registration")
    student_user = request_json(
        "/api/v1/identity/auth/register",
        method="POST",
        body={
            "email": student_email,
            "password": shared_credential,
            "timezone": "UTC",
        },
        expected=201,
    )

    print("Smoke: future teacher registration as student")
    teacher_user = request_json(
        "/api/v1/identity/auth/register",
        method="POST",
        body={
            "email": teacher_email,
            "password": shared_credential,
            "timezone": "UTC",
        },
        expected=201,
    )

    print("Smoke: role login")
    admin_login = request_json(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": admin_email, "password": admin_password},
        expected=200,
    )
    admin_token = str(admin_login["access_token"])
    admin_me = request_json(
        "/api/v1/identity/users/me",
        headers=auth_headers(admin_token),
        expected=200,
    )
    admin_role = admin_me.get("role")
    if not isinstance(admin_role, dict) or str(admin_role.get("name")) != "admin":
        raise RuntimeError("Configured smoke admin account does not have admin role")

    teacher_user_id = str(teacher_user["id"])

    print("Smoke: admin promotes existing user to teacher")
    request_json(
        f"/api/v1/admin/users/{teacher_user_id}/role",
        method="POST",
        headers=auth_headers(admin_token),
        body={
            "role": "teacher",
        },
        expected=200,
    )

    teacher_login = request_json(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": teacher_email, "password": shared_credential},
        expected=200,
    )
    student_login = request_json(
        "/api/v1/identity/auth/login",
        method="POST",
        body={"email": student_email, "password": shared_credential},
        expected=200,
    )

    teacher_token = str(teacher_login["access_token"])
    student_token = str(student_login["access_token"])

    print("Smoke: student profile check")
    student_me = request_json(
        "/api/v1/identity/users/me",
        headers=auth_headers(student_token),
        expected=200,
    )
    ensure(
        str(student_me.get("id")) == str(student_user["id"]),
        "Student /users/me did not return expected user id",
    )

    print("Smoke: admin teacher moderation list")
    teacher_query = urlencode(
        {"q": teacher_email, "limit": 10, "offset": 0},
    )
    admin_teachers = request_json(
        f"/api/v1/admin/teachers?{teacher_query}",
        headers=auth_headers(admin_token),
        expected=200,
    )
    admin_teacher_items = extract_page_items(admin_teachers, "/api/v1/admin/teachers")
    ensure(
        any(str(item.get("teacher_id")) == teacher_user_id for item in admin_teacher_items),
        "Admin teacher list did not include newly created teacher",
    )
    request_json(
        f"/api/v1/admin/teachers/{teacher_user_id}",
        headers=auth_headers(admin_token),
        expected=200,
    )

    print("Smoke: admin slot/package setup")
    slot_start = (now_utc + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)
    slot_end = slot_start + timedelta(minutes=30)
    created_slot = request_json(
        "/api/v1/admin/slots",
        method="POST",
        headers=auth_headers(admin_token),
        body={
            "teacher_id": teacher_user_id,
            "start_at_utc": slot_start.isoformat(),
            "end_at_utc": slot_end.isoformat(),
        },
        expected=201,
    )

    created_package = request_json(
        "/api/v1/admin/packages",
        method="POST",
        headers=auth_headers(admin_token),
        body={
            "student_id": str(student_user["id"]),
            "lessons_total": 2,
            "expires_at_utc": (now_utc + timedelta(days=30)).isoformat(),
            "price_amount": "120.00",
            "price_currency": "USD",
        },
        expected=201,
    )

    print("Smoke: student open-slots and booking flow")
    open_slots_query = urlencode(
        {"teacher_id": teacher_user_id, "limit": 20, "offset": 0},
    )
    open_slots_page = request_json(
        f"/api/v1/scheduling/slots/open?{open_slots_query}",
        expected=200,
    )
    open_slots = extract_page_items(open_slots_page, "/api/v1/scheduling/slots/open")
    ensure(
        any(str(item.get("id")) == str(created_slot["slot_id"]) for item in open_slots),
        "Created slot did not appear in open slots list",
    )

    hold_booking = request_json(
        "/api/v1/booking/hold",
        method="POST",
        headers=auth_headers(student_token),
        body={
            "slot_id": str(created_slot["slot_id"]),
            "package_id": str(created_package["package_id"]),
        },
        expected=200,
    )
    confirmed_booking = request_json(
        f"/api/v1/booking/{hold_booking['id']}/confirm",
        method="POST",
        headers=auth_headers(student_token),
        expected=200,
    )
    ensure(
        str(confirmed_booking.get("status")) == "confirmed",
        "Booking confirm smoke check failed",
    )

    print("Smoke: role-specific booking/package visibility")
    student_bookings_page = request_json(
        "/api/v1/booking/my?limit=20&offset=0",
        headers=auth_headers(student_token),
        expected=200,
    )
    student_bookings = extract_page_items(student_bookings_page, "/api/v1/booking/my (student)")
    ensure(
        any(str(item.get("id")) == str(confirmed_booking["id"]) for item in student_bookings),
        "Student bookings list does not include confirmed booking",
    )

    teacher_bookings_page = request_json(
        "/api/v1/booking/my?limit=20&offset=0",
        headers=auth_headers(teacher_token),
        expected=200,
    )
    teacher_bookings = extract_page_items(teacher_bookings_page, "/api/v1/booking/my (teacher)")
    ensure(
        any(str(item.get("id")) == str(confirmed_booking["id"]) for item in teacher_bookings),
        "Teacher bookings list does not include confirmed booking",
    )

    student_packages_page = request_json(
        f"/api/v1/billing/packages/students/{student_user['id']}?limit=20&offset=0",
        headers=auth_headers(student_token),
        expected=200,
    )
    student_packages = extract_page_items(
        student_packages_page,
        "/api/v1/billing/packages/students/{student_id}",
    )
    ensure(
        any(str(item.get("id")) == str(created_package["package_id"]) for item in student_packages),
        "Student packages list does not include admin-created package",
    )

    print("Smoke: admin operational read models")
    admin_bookings_query = urlencode(
        {
            "teacher_id": teacher_user_id,
            "student_id": str(student_user["id"]),
            "limit": 20,
            "offset": 0,
        },
    )
    admin_bookings_page = request_json(
        f"/api/v1/admin/bookings?{admin_bookings_query}",
        headers=auth_headers(admin_token),
        expected=200,
    )
    admin_bookings = extract_page_items(admin_bookings_page, "/api/v1/admin/bookings")
    ensure(
        any(str(item.get("booking_id")) == str(confirmed_booking["id"]) for item in admin_bookings),
        "Admin bookings list does not include confirmed booking",
    )

    admin_packages_query = urlencode(
        {
            "student_id": str(student_user["id"]),
            "limit": 20,
            "offset": 0,
        },
    )
    admin_packages_page = request_json(
        f"/api/v1/admin/packages?{admin_packages_query}",
        headers=auth_headers(admin_token),
        expected=200,
    )
    admin_packages = extract_page_items(admin_packages_page, "/api/v1/admin/packages")
    ensure(
        any(
            str(item.get("package_id")) == str(created_package["package_id"])
            for item in admin_packages
        ),
        "Admin packages list does not include created package",
    )

    request_json(
        "/api/v1/admin/kpi/overview",
        headers=auth_headers(admin_token),
        expected=200,
    )
    sales_query = urlencode(
        {
            "from_utc": (now_utc - timedelta(days=30)).isoformat(),
            "to_utc": now_utc.isoformat(),
        },
    )
    request_json(
        f"/api/v1/admin/kpi/sales?{sales_query}",
        headers=auth_headers(admin_token),
        expected=200,
    )

    print("Role-based release gate passed.")
    request_json(
        f"/api/v1/booking/{confirmed_booking['id']}/cancel",
        method="POST",
        headers=auth_headers(admin_token),
        body={"reason": "release gate cleanup"},
        expected=200,
    )
    print("Smoke checks passed.")


if __name__ == "__main__":
    main()
