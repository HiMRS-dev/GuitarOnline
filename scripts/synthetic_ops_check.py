#!/usr/bin/env python3
"""Periodic synthetic ops check with critical-path validation and alerting."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_ALERTMANAGER_URL = "http://alertmanager:9093"
DEFAULT_RUNBOOK_URL = "ops/release_checklist.md"
DEFAULT_PASSWORD = "StrongPass123!"


class SyntheticCheckError(RuntimeError):
    """Structured synthetic check failure."""

    def __init__(self, step: str, message: str):
        super().__init__(f"[{step}] {message}")
        self.step = step
        self.message = message


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    access_token: str
    email: str


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _request(
    base_url: str,
    path: str,
    *,
    expected: set[int],
    timeout_seconds: int,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    payload = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    request_obj = urllib.request.Request(
        f"{base_url}{path}",
        data=payload,
        method=method,
        headers=req_headers,
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=timeout_seconds) as response:  # noqa: S310
            content = response.read()
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        status = exc.code
        content = exc.read()
        if status not in expected:
            body_text = content.decode("utf-8", errors="ignore")
            raise RuntimeError(f"{method} {path} -> {status}: {body_text}") from exc
        return status, content
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc

    if status not in expected:
        raise RuntimeError(f"{method} {path} -> {status}, expected one of {sorted(expected)}")
    return status, content


def _request_json(
    base_url: str,
    path: str,
    *,
    expected: set[int],
    timeout_seconds: int,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    status, content = _request(
        base_url,
        path,
        expected=expected,
        timeout_seconds=timeout_seconds,
        method=method,
        body=body,
        headers=headers,
    )
    if not content:
        return status, {}
    return status, json.loads(content.decode("utf-8"))


def _ensure_user(
    base_url: str,
    *,
    role: str,
    email: str,
    password: str,
    timeout_seconds: int,
) -> AuthContext:
    status, _ = _request_json(
        base_url,
        "/api/v1/identity/auth/register",
        method="POST",
        expected={201, 409},
        timeout_seconds=timeout_seconds,
        body={
            "email": email,
            "password": password,
            "timezone": "UTC",
            "role": role,
        },
    )
    if status not in {201, 409}:
        raise RuntimeError(f"Unexpected registration status for {email}: {status}")

    _, login_payload = _request_json(
        base_url,
        "/api/v1/identity/auth/login",
        method="POST",
        expected={200},
        timeout_seconds=timeout_seconds,
        body={"email": email, "password": password},
    )
    token = str(login_payload["access_token"])
    _, me_payload = _request_json(
        base_url,
        "/api/v1/identity/users/me",
        expected={200},
        timeout_seconds=timeout_seconds,
        headers=_auth_headers(token),
    )
    return AuthContext(
        user_id=str(me_payload["id"]),
        access_token=token,
        email=email,
    )


def _post_alerts_v2(
    alertmanager_url: str,
    payload: list[dict[str, object]],
    timeout_seconds: int,
) -> None:
    body = json.dumps(payload).encode("utf-8")
    request_obj = urllib.request.Request(
        f"{alertmanager_url.rstrip('/')}/api/v2/alerts",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=timeout_seconds):  # noqa: S310
            return
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"POST /api/v2/alerts failed with HTTP {exc.code}: {detail}",
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST /api/v2/alerts failed: {exc.reason}") from exc


def _emit_failure_alert(
    alertmanager_url: str,
    *,
    step: str,
    detail: str,
    runbook_url: str,
    base_url: str,
    alert_duration_minutes: int,
    timeout_seconds: int,
) -> None:
    now = datetime.now(UTC)
    payload = [
        {
            "labels": {
                "alertname": "GuitarOnlineSyntheticOpsCheckFailed",
                "severity": "critical",
                "service": "guitaronline-api",
                "source": "synthetic_ops_check",
            },
            "annotations": {
                "summary": f"Synthetic ops check failed at step: {step}",
                "description": detail,
                "runbook": runbook_url,
                "base_url": base_url,
            },
            "startsAt": now.isoformat().replace("+00:00", "Z"),
            "endsAt": (now + timedelta(minutes=alert_duration_minutes))
            .isoformat()
            .replace("+00:00", "Z"),
        }
    ]
    _post_alerts_v2(alertmanager_url, payload, timeout_seconds)


def _create_slot_with_retry(
    base_url: str,
    *,
    admin_token: str,
    teacher_id: str,
    initial_start: datetime,
    timeout_seconds: int,
    max_attempts: int = 8,
) -> dict[str, object]:
    for attempt in range(max_attempts):
        slot_start = initial_start + timedelta(minutes=65 * attempt)
        slot_end = slot_start + timedelta(minutes=30)
        status, payload = _request_json(
            base_url,
            "/api/v1/admin/slots",
            method="POST",
            expected={201, 409},
            timeout_seconds=timeout_seconds,
            headers=_auth_headers(admin_token),
            body={
                "teacher_id": teacher_id,
                "start_at_utc": slot_start.isoformat(),
                "end_at_utc": slot_end.isoformat(),
            },
        )
        if status == 201:
            return payload
    raise RuntimeError(
        f"Failed to create synthetic slot after {max_attempts} attempts due overlap/conflict",
    )


def run_synthetic_ops_check(
    *,
    base_url: str,
    timeout_seconds: int,
    admin_email: str,
    teacher_email: str,
    student_email: str,
    password: str,
) -> None:
    for endpoint in ["/health", "/ready", "/metrics"]:
        try:
            _, content = _request(
                base_url,
                endpoint,
                expected={200},
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - operational script
            raise SyntheticCheckError("availability", str(exc)) from exc
        if endpoint == "/metrics":
            metrics_text = content.decode("utf-8", errors="ignore")
            required = (
                "guitaronline_http_requests_total",
                "guitaronline_http_request_duration_seconds",
            )
            missing = [name for name in required if name not in metrics_text]
            if missing:
                raise SyntheticCheckError(
                    "metrics",
                    f"Required metrics are missing: {', '.join(missing)}",
                )

    try:
        admin = _ensure_user(
            base_url,
            role="admin",
            email=admin_email,
            password=password,
            timeout_seconds=timeout_seconds,
        )
        teacher = _ensure_user(
            base_url,
            role="teacher",
            email=teacher_email,
            password=password,
            timeout_seconds=timeout_seconds,
        )
        student = _ensure_user(
            base_url,
            role="student",
            email=student_email,
            password=password,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - operational script
        raise SyntheticCheckError("auth", str(exc)) from exc

    try:
        _request_json(
            base_url,
            "/api/v1/teachers/profiles",
            method="POST",
            expected={201, 409},
            timeout_seconds=timeout_seconds,
            headers=_auth_headers(teacher.access_token),
            body={
                "user_id": teacher.user_id,
                "display_name": "Synthetic Ops Teacher",
                "bio": "Synthetic periodic ops check profile",
                "experience_years": 3,
            },
        )
    except Exception as exc:  # pragma: no cover - operational script
        raise SyntheticCheckError("teacher_profile", str(exc)) from exc

    try:
        teacher_query = urlencode({"q": "Synthetic Ops Teacher", "limit": 5, "offset": 0})
        _, teachers_page = _request_json(
            base_url,
            f"/api/v1/admin/teachers?{teacher_query}",
            expected={200},
            timeout_seconds=timeout_seconds,
            headers=_auth_headers(admin.access_token),
        )
        if int(teachers_page.get("total", 0)) < 1:
            raise RuntimeError("Admin teacher list returned no matching teachers")
    except Exception as exc:  # pragma: no cover - operational script
        raise SyntheticCheckError("admin_teachers_list", str(exc)) from exc

    try:
        run_id = uuid4().hex
        jitter_minutes = int(run_id[:4], 16) % 720
        initial_slot_start = (
            datetime.now(UTC)
            .replace(second=0, microsecond=0)
            + timedelta(hours=30, minutes=jitter_minutes)
        )
        created_slot = _create_slot_with_retry(
            base_url,
            admin_token=admin.access_token,
            teacher_id=teacher.user_id,
            initial_start=initial_slot_start,
            timeout_seconds=timeout_seconds,
        )
        _, created_package = _request_json(
            base_url,
            "/api/v1/admin/packages",
            method="POST",
            expected={201},
            timeout_seconds=timeout_seconds,
            headers=_auth_headers(admin.access_token),
            body={
                "student_id": student.user_id,
                "lessons_total": 1,
                "expires_at_utc": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
                "price_amount": "10.00",
                "price_currency": "USD",
            },
        )
        _, hold_booking = _request_json(
            base_url,
            "/api/v1/booking/hold",
            method="POST",
            expected={200},
            timeout_seconds=timeout_seconds,
            headers=_auth_headers(student.access_token),
            body={
                "slot_id": str(created_slot["slot_id"]),
                "package_id": str(created_package["package_id"]),
            },
        )
        _, confirmed = _request_json(
            base_url,
            f"/api/v1/booking/{hold_booking['id']}/confirm",
            method="POST",
            expected={200},
            timeout_seconds=timeout_seconds,
            headers=_auth_headers(student.access_token),
        )
        if confirmed.get("status") != "confirmed":
            raise RuntimeError("Expected confirmed booking status after confirm")

        _, canceled = _request_json(
            base_url,
            f"/api/v1/booking/{hold_booking['id']}/cancel",
            method="POST",
            expected={200},
            timeout_seconds=timeout_seconds,
            headers=_auth_headers(student.access_token),
            body={"reason": "Synthetic ops periodic check cleanup"},
        )
        if canceled.get("status") != "canceled":
            raise RuntimeError("Expected canceled booking status after cleanup cancel")
    except Exception as exc:  # pragma: no cover - operational script
        raise SyntheticCheckError("booking_flow", str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run synthetic operational critical-path checks. On failure, emit a "
            "critical alert to Alertmanager."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("SYNTHETIC_OPS_BASE_URL", DEFAULT_BASE_URL),
        help="API base URL without trailing slash (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--alertmanager-url",
        default=os.getenv("SYNTHETIC_OPS_ALERTMANAGER_URL", DEFAULT_ALERTMANAGER_URL),
        help="Alertmanager URL (default: http://alertmanager:9093).",
    )
    parser.add_argument(
        "--alert-duration-minutes",
        type=int,
        default=int(os.getenv("SYNTHETIC_OPS_ALERT_DURATION_MINUTES", "30")),
        help="Failure alert TTL in minutes (default: 30).",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=int(os.getenv("SYNTHETIC_OPS_REQUEST_TIMEOUT_SECONDS", "30")),
        help="HTTP timeout for each request (default: 30).",
    )
    parser.add_argument(
        "--runbook-url",
        default=os.getenv("SYNTHETIC_OPS_RUNBOOK_URL", DEFAULT_RUNBOOK_URL),
        help="Runbook reference included in alert annotations.",
    )
    parser.add_argument(
        "--admin-email",
        default=os.getenv("SYNTHETIC_OPS_ADMIN_EMAIL", "synthetic-ops-admin@guitaronline.dev"),
        help="Synthetic admin account email.",
    )
    parser.add_argument(
        "--teacher-email",
        default=os.getenv("SYNTHETIC_OPS_TEACHER_EMAIL", "synthetic-ops-teacher@guitaronline.dev"),
        help="Synthetic teacher account email.",
    )
    parser.add_argument(
        "--student-email",
        default=os.getenv("SYNTHETIC_OPS_STUDENT_EMAIL", "synthetic-ops-student@guitaronline.dev"),
        help="Synthetic student account email.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SYNTHETIC_OPS_PASSWORD", DEFAULT_PASSWORD),
        help="Shared password for synthetic accounts.",
    )
    parser.add_argument(
        "--no-alert-on-failure",
        action="store_true",
        help="Do not emit Alertmanager alert on failure (debug mode).",
    )
    args = parser.parse_args()

    if args.alert_duration_minutes <= 0:
        raise ValueError("--alert-duration-minutes must be greater than 0")
    if args.request_timeout_seconds <= 0:
        raise ValueError("--request-timeout-seconds must be greater than 0")

    base_url = args.base_url.rstrip("/")
    alertmanager_url = args.alertmanager_url.rstrip("/")

    try:
        run_synthetic_ops_check(
            base_url=base_url,
            timeout_seconds=args.request_timeout_seconds,
            admin_email=args.admin_email,
            teacher_email=args.teacher_email,
            student_email=args.student_email,
            password=args.password,
        )
    except SyntheticCheckError as exc:
        print(f"Synthetic ops check failed at step={exc.step}: {exc.message}")
        if not args.no_alert_on_failure:
            try:
                _emit_failure_alert(
                    alertmanager_url,
                    step=exc.step,
                    detail=exc.message,
                    runbook_url=args.runbook_url,
                    base_url=base_url,
                    alert_duration_minutes=args.alert_duration_minutes,
                    timeout_seconds=args.request_timeout_seconds,
                )
                print("Failure alert submitted to Alertmanager.")
            except Exception as alert_exc:  # pragma: no cover - operational script
                print(f"Failed to submit failure alert: {alert_exc}")
        return 1
    except Exception as exc:  # pragma: no cover - operational script
        print(f"Synthetic ops check failed with unexpected error: {exc}")
        if not args.no_alert_on_failure:
            try:
                _emit_failure_alert(
                    alertmanager_url,
                    step="unexpected_error",
                    detail=str(exc),
                    runbook_url=args.runbook_url,
                    base_url=base_url,
                    alert_duration_minutes=args.alert_duration_minutes,
                    timeout_seconds=args.request_timeout_seconds,
                )
                print("Failure alert submitted to Alertmanager.")
            except Exception as alert_exc:
                print(f"Failed to submit failure alert: {alert_exc}")
        return 1

    print("Synthetic ops check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
