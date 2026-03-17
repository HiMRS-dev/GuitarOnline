"""Generate ~1000 slots and verify admin slots endpoint response envelope."""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlencode
from uuid import uuid4

BASE_URL = os.getenv("LOAD_SANITY_BASE_URL", "http://localhost:8000").rstrip("/")
TARGET_SLOTS = int(os.getenv("LOAD_SANITY_TARGET_SLOTS", "1000"))
SLOT_DURATION_MINUTES = 60
WORKDAY_START = time(hour=9, minute=0)
WORKDAY_END = time(hour=17, minute=0)
WEEKDAYS = [0, 1, 2, 3, 4]
MAX_BULK_CANDIDATES = 1000


def _guard_non_test_execution() -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env in {"test", "testing"}:
        return
    raise RuntimeError(
        "Refusing to run load sanity outside APP_ENV=test "
        f"(APP_ENV={app_env or 'unset'}, base_url={BASE_URL}).",
    )


def request(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    expected: int = 200,
) -> bytes:
    payload = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=payload,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()
            status = response.getcode()
    except urllib.error.HTTPError as exc:  # pragma: no cover - runtime script
        payload_text = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {payload_text}") from exc

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
    return json.loads(
        request(
            path,
            method=method,
            body=body,
            headers=headers,
            expected=expected,
        ).decode("utf-8"),
    )


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _next_monday(current_date: date) -> date:
    days_ahead = (7 - current_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return current_date + timedelta(days=days_ahead)


def main() -> None:
    _guard_non_test_execution()

    if TARGET_SLOTS <= 0:
        raise RuntimeError("LOAD_SANITY_TARGET_SLOTS must be > 0")

    workday_minutes = (
        WORKDAY_END.hour * 60
        + WORKDAY_END.minute
        - WORKDAY_START.hour * 60
        - WORKDAY_START.minute
    )
    slots_per_day = int(workday_minutes / SLOT_DURATION_MINUTES)
    if slots_per_day <= 0:
        raise RuntimeError("Invalid workday window for slot generation")

    slots_per_week = slots_per_day * len(WEEKDAYS)
    weeks_required = max(1, math.ceil(TARGET_SLOTS / slots_per_week))
    candidate_slots = weeks_required * slots_per_week
    if candidate_slots > MAX_BULK_CANDIDATES:
        raise RuntimeError(
            "Requested load target exceeds bulk-create safety limit. "
            f"target={TARGET_SLOTS}, candidates={candidate_slots}, max={MAX_BULK_CANDIDATES}",
        )

    base_date = _next_monday(datetime.now(UTC).date())
    date_from = base_date
    date_to = base_date + timedelta(days=weeks_required * 7 - 1)

    suffix = uuid4().hex[:10]
    password = "StrongPass123!"
    admin_email = f"load-sanity-admin-{suffix}@guitaronline.dev"
    teacher_email = f"load-sanity-teacher-{suffix}@guitaronline.dev"

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

    request_json(
        "/api/v1/teachers/profiles",
        method="POST",
        headers=auth_headers(str(teacher_login["access_token"])),
        body={
            "user_id": str(teacher_user["id"]),
            "display_name": "Load Sanity Teacher",
            "bio": "Generated by load sanity script",
            "experience_years": 5,
        },
        expected=201,
    )

    admin_token = str(admin_login["access_token"])
    created_count = 0
    skipped_count = 0
    run_mode = "admin_bulk_create"
    try:
        bulk_result = request_json(
            "/api/v1/admin/slots/bulk-create",
            method="POST",
            headers=auth_headers(admin_token),
            body={
                "teacher_id": str(teacher_user["id"]),
                "date_from_utc": date_from.isoformat(),
                "date_to_utc": date_to.isoformat(),
                "weekdays": WEEKDAYS,
                "start_time_utc": WORKDAY_START.isoformat(),
                "end_time_utc": WORKDAY_END.isoformat(),
                "slot_duration_minutes": SLOT_DURATION_MINUTES,
                "exclude_dates": [],
                "exclude_time_ranges": [],
            },
            expected=200,
        )
        created_count = int(bulk_result.get("created_count", 0))
        skipped_count = int(bulk_result.get("skipped_count", 0))
        if created_count + skipped_count != candidate_slots:
            raise RuntimeError(
                "Bulk-create result mismatch: "
                f"created={created_count}, skipped={skipped_count}, candidates={candidate_slots}",
            )
    except RuntimeError as error:
        if "-> 404" not in str(error):
            raise

        run_mode = "legacy_slot_create"
        start_cursor = date_from
        while start_cursor <= date_to:
            if start_cursor.weekday() in WEEKDAYS:
                slot_start = datetime.combine(start_cursor, WORKDAY_START, tzinfo=UTC)
                slot_end_bound = datetime.combine(start_cursor, WORKDAY_END, tzinfo=UTC)
                while slot_start + timedelta(minutes=SLOT_DURATION_MINUTES) <= slot_end_bound:
                    slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
                    try:
                        request_json(
                            "/api/v1/scheduling/slots",
                            method="POST",
                            headers=auth_headers(admin_token),
                            body={
                                "teacher_id": str(teacher_user["id"]),
                                "start_at": slot_start.isoformat(),
                                "end_at": slot_end.isoformat(),
                            },
                            expected=201,
                        )
                        created_count += 1
                    except RuntimeError as create_error:
                        if "-> 422" in str(create_error):
                            skipped_count += 1
                        else:
                            raise RuntimeError(str(create_error)) from create_error
                    slot_start = slot_end
            start_cursor += timedelta(days=1)

        if created_count + skipped_count != candidate_slots:
            raise RuntimeError(
                "Legacy slot-create result mismatch: "
                f"created={created_count}, skipped={skipped_count}, candidates={candidate_slots}",
            ) from error

    if created_count < TARGET_SLOTS:
        raise RuntimeError(
            "Bulk-create produced fewer slots than target: "
            f"target={TARGET_SLOTS}, created={created_count}",
        )

    from_utc = datetime.combine(date_from, time.min, tzinfo=UTC)
    to_utc = datetime.combine(date_to, time.max.replace(microsecond=0), tzinfo=UTC)
    if run_mode == "admin_bulk_create":
        query = urlencode(
            {
                "teacher_id": str(teacher_user["id"]),
                "from_utc": from_utc.isoformat(),
                "to_utc": to_utc.isoformat(),
                "limit": 100,
                "offset": 0,
            },
        )
        slots_page = request_json(
            f"/api/v1/admin/slots?{query}",
            headers=auth_headers(admin_token),
            expected=200,
        )
    else:
        query = urlencode(
            {
                "teacher_id": str(teacher_user["id"]),
                "limit": 100,
                "offset": 0,
            },
        )
        slots_page = request_json(
            f"/api/v1/scheduling/slots/open?{query}",
            headers=auth_headers(admin_token),
            expected=200,
        )

    if not isinstance(slots_page.get("items"), list):
        raise RuntimeError("Admin slots endpoint returned invalid items envelope")
    if not isinstance(slots_page.get("total"), int):
        raise RuntimeError("Admin slots endpoint returned invalid total envelope")
    if int(slots_page["total"]) < TARGET_SLOTS:
        raise RuntimeError(
            "Admin slots endpoint total is below requested target: "
            f"target={TARGET_SLOTS}, total={slots_page['total']}",
        )

    print(
        "Load sanity passed "
        f"(mode={run_mode}, target={TARGET_SLOTS}, candidates={candidate_slots}, "
        f"created={created_count}, skipped={skipped_count}, listed_total={slots_page['total']}).",
    )


if __name__ == "__main__":
    main()
