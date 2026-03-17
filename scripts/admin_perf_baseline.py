#!/usr/bin/env python3
"""Benchmark admin-heavy endpoints and write a baseline report."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as time_of_day
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PASSWORD = "StrongPass123!"
DEFAULT_WARMUP = 5
DEFAULT_ITERATIONS = 30
DEFAULT_TARGET_SLOTS = 600
DEFAULT_TEACHERS_COUNT = 10
MAX_BULK_CANDIDATES = 1000


def _guard_non_test_execution(*, base_url: str, allow_non_test: bool) -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env in {"test", "testing"} or allow_non_test:
        return
    raise RuntimeError(
        "Refusing to run admin perf baseline outside APP_ENV=test "
        f"(APP_ENV={app_env or 'unset'}, base_url={base_url}). "
        "Re-run with --allow-non-test only if this is intentional.",
    )


def _request(
    base_url: str,
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
        f"{base_url}{path}",
        method=method,
        data=payload,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:  # noqa: S310
            status = response.getcode()
            content = response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - runtime script
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - runtime script
        raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc

    if status != expected:
        raise RuntimeError(f"{method} {path} -> {status}, expected {expected}")
    return content


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    expected: int = 200,
) -> dict[str, object]:
    return json.loads(
        _request(
            base_url,
            path,
            method=method,
            body=body,
            headers=headers,
            expected=expected,
        ).decode("utf-8"),
    )


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _identity_with_retry(
    *,
    base_url: str,
    path: str,
    body: dict[str, object],
    action: str,
    max_attempts: int = 12,
) -> dict[str, object]:
    for attempt in range(max_attempts):
        try:
            return _request_json(
                base_url,
                path,
                method="POST",
                expected=200 if "login" in path else 201,
                body=body,
            )
        except RuntimeError as exc:
            if "-> 429" not in str(exc):
                raise
            wait_seconds = 5
            retry_match = re.search(r"(\d+)\s+second", str(exc))
            if retry_match:
                wait_seconds = int(retry_match.group(1)) + 1
            print(
                f"Rate-limited during {action} (attempt={attempt + 1}/{max_attempts}). "
                f"Sleeping {wait_seconds}s...",
            )
            time.sleep(wait_seconds)
    raise RuntimeError(f"Exceeded retry budget for identity action: {action}")


def _next_monday(current_date: date) -> date:
    days_ahead = (7 - current_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return current_date + timedelta(days=days_ahead)


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise RuntimeError("No values for percentile calculation")
    rank = max(1, math.ceil(q * len(sorted_values)))
    return sorted_values[rank - 1]


@dataclass(frozen=True)
class BenchResult:
    endpoint: str
    path: str
    samples: int
    min_ms: float
    avg_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float


def _benchmark(
    *,
    name: str,
    path: str,
    base_url: str,
    access_token: str,
    warmup: int,
    iterations: int,
    validator: Callable[[dict[str, object]], None],
) -> BenchResult:
    headers = _auth_headers(access_token)
    for _ in range(warmup):
        payload = _request_json(base_url, path, headers=headers, expected=200)
        validator(payload)

    samples_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        payload = _request_json(base_url, path, headers=headers, expected=200)
        validator(payload)
        duration_ms = (time.perf_counter() - started) * 1000.0
        samples_ms.append(duration_ms)

    sorted_samples = sorted(samples_ms)
    return BenchResult(
        endpoint=name,
        path=path,
        samples=len(samples_ms),
        min_ms=round(min(sorted_samples), 2),
        avg_ms=round(statistics.fmean(sorted_samples), 2),
        p50_ms=round(_percentile(sorted_samples, 0.50), 2),
        p95_ms=round(_percentile(sorted_samples, 0.95), 2),
        max_ms=round(max(sorted_samples), 2),
    )


def _write_report_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_report_md(path: Path, payload: dict[str, object]) -> None:
    benchmarks = payload["benchmarks"]
    lines = [
        "# Admin Endpoint Performance Baseline",
        "",
        f"- Generated at (UTC): `{payload['generated_at_utc']}`",
        f"- Base URL: `{payload['base_url']}`",
        f"- Warmup requests per endpoint: `{payload['config']['warmup']}`",
        f"- Measured requests per endpoint: `{payload['config']['iterations']}`",
        f"- Synthetic teacher profiles created: `{payload['dataset']['teachers_created']}`",
        f"- Synthetic slots created: `{payload['dataset']['slots_created']}`",
        "",
        "## Results",
        "",
        "| Endpoint | Avg (ms) | P50 (ms) | P95 (ms) | Max (ms) | Samples |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in benchmarks:
        lines.append(
            "| "
            f"`{item['endpoint']}` | {item['avg_ms']:.2f} | {item['p50_ms']:.2f} | "
            f"{item['p95_ms']:.2f} | {item['max_ms']:.2f} | {item['samples']} |",
        )
    lines.extend(
        [
            "",
            "## Endpoints",
            "",
        ],
    )
    for item in benchmarks:
        lines.append(f"- `{item['endpoint']}`: `{item['path']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run admin endpoint latency baseline.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--target-slots", type=int, default=DEFAULT_TARGET_SLOTS)
    parser.add_argument("--teachers-count", type=int, default=DEFAULT_TEACHERS_COUNT)
    parser.add_argument(
        "--allow-non-test",
        action="store_true",
        help="Allow execution when APP_ENV is not test.",
    )
    parser.add_argument(
        "--output-json",
        default="docs/perf/admin_perf_baseline_2026-03-06.json",
    )
    parser.add_argument(
        "--output-md",
        default="docs/perf/admin_perf_baseline_2026-03-06.md",
    )
    args = parser.parse_args()

    if args.warmup < 0:
        raise RuntimeError("--warmup must be >= 0")
    if args.iterations <= 0:
        raise RuntimeError("--iterations must be > 0")
    if args.target_slots <= 0:
        raise RuntimeError("--target-slots must be > 0")
    if args.teachers_count <= 0:
        raise RuntimeError("--teachers-count must be > 0")

    base_url = args.base_url.rstrip("/")
    _guard_non_test_execution(base_url=base_url, allow_non_test=args.allow_non_test)

    suffix = uuid4().hex[:10]
    shared_credential = DEFAULT_PASSWORD
    admin_email = f"perf-baseline-admin-{suffix}@guitaronline.dev"

    workday_start = time_of_day(hour=9, minute=0)
    workday_end = time_of_day(hour=17, minute=0)
    slot_duration_minutes = 60
    weekdays = [0, 1, 2, 3, 4]
    slots_per_day = int((workday_end.hour - workday_start.hour) * 60 / slot_duration_minutes)
    slots_per_week = slots_per_day * len(weekdays)
    weeks_required = max(1, math.ceil(args.target_slots / slots_per_week))
    candidate_slots = weeks_required * slots_per_week
    if candidate_slots > MAX_BULK_CANDIDATES:
        raise RuntimeError(
            "Requested slot target exceeds bulk-create cap: "
            f"target={args.target_slots}, candidates={candidate_slots}, max={MAX_BULK_CANDIDATES}",
        )

    base_date = _next_monday(datetime.now(UTC).date())
    date_from = base_date
    date_to = base_date + timedelta(days=weeks_required * 7 - 1)
    from_utc = datetime.combine(date_from, time_of_day.min, tzinfo=UTC).replace(microsecond=0)
    to_utc = datetime.combine(date_to, time_of_day.max, tzinfo=UTC).replace(microsecond=0)

    _identity_with_retry(
        base_url=base_url,
        path="/api/v1/identity/auth/register",
        action="admin registration",
        body={
            "email": admin_email,
            "password": shared_credential,
            "timezone": "UTC",
            "role": "admin",
        },
    )
    admin_login = _identity_with_retry(
        base_url=base_url,
        path="/api/v1/identity/auth/login",
        action="admin login",
        body={"email": admin_email, "password": shared_credential},
    )
    admin_token = str(admin_login["access_token"])

    teacher_ids: list[str] = []
    teacher_query_token = f"perf-baseline-{suffix}"
    for index in range(args.teachers_count):
        teacher_email = f"perf-baseline-teacher-{suffix}-{index}@guitaronline.dev"
        teacher_user = _identity_with_retry(
            base_url=base_url,
            path="/api/v1/identity/auth/register",
            action=f"teacher registration #{index}",
            body={
                "email": teacher_email,
                "password": shared_credential,
                "timezone": "UTC",
                "role": "teacher",
            },
        )
        teacher_login = _identity_with_retry(
            base_url=base_url,
            path="/api/v1/identity/auth/login",
            action=f"teacher login #{index}",
            body={"email": teacher_email, "password": shared_credential},
        )
        _request_json(
            base_url,
            "/api/v1/teachers/profiles",
            method="POST",
            expected=201,
            headers=_auth_headers(str(teacher_login["access_token"])),
            body={
                "user_id": str(teacher_user["id"]),
                "display_name": f"Perf Baseline Teacher {teacher_query_token} {index}",
                "bio": "Synthetic profile for admin perf baseline",
                "experience_years": 5,
            },
        )
        teacher_ids.append(str(teacher_user["id"]))

    heavy_teacher_id = teacher_ids[0]
    bulk_result = _request_json(
        base_url,
        "/api/v1/admin/slots/bulk-create",
        method="POST",
        expected=200,
        headers=_auth_headers(admin_token),
        body={
            "teacher_id": heavy_teacher_id,
            "date_from_utc": date_from.isoformat(),
            "date_to_utc": date_to.isoformat(),
            "weekdays": weekdays,
            "start_time_utc": workday_start.isoformat(),
            "end_time_utc": workday_end.isoformat(),
            "slot_duration_minutes": slot_duration_minutes,
            "exclude_dates": [],
            "exclude_time_ranges": [],
        },
    )
    slots_created = int(bulk_result.get("created_count", 0))
    if slots_created < args.target_slots:
        raise RuntimeError(
            "Bulk slot generation created fewer slots than requested target: "
            f"target={args.target_slots}, created={slots_created}",
        )

    teachers_path = "/api/v1/admin/teachers?" + urlencode(
        {"q": teacher_query_token, "limit": 100, "offset": 0},
    )
    slots_path = "/api/v1/admin/slots?" + urlencode(
        {
            "teacher_id": heavy_teacher_id,
            "from_utc": from_utc.isoformat(),
            "to_utc": to_utc.isoformat(),
            "limit": 100,
            "offset": 0,
        },
    )
    overview_path = "/api/v1/admin/kpi/overview"
    sales_from = (datetime.now(UTC) - timedelta(days=180)).replace(microsecond=0).isoformat()
    sales_to = datetime.now(UTC).replace(microsecond=0).isoformat()
    sales_path = "/api/v1/admin/kpi/sales?" + urlencode(
        {
            "from_utc": sales_from,
            "to_utc": sales_to,
        },
    )

    def _validate_teachers(payload: dict[str, object]) -> None:
        if not isinstance(payload.get("total"), int):
            raise RuntimeError("Unexpected /admin/teachers payload: missing integer total")
        if int(payload["total"]) < args.teachers_count:
            raise RuntimeError(
                "Unexpected /admin/teachers total below synthetic set: "
                f"total={payload['total']}, expected>={args.teachers_count}",
            )

    def _validate_slots(payload: dict[str, object]) -> None:
        if not isinstance(payload.get("total"), int):
            raise RuntimeError("Unexpected /admin/slots payload: missing integer total")
        if int(payload["total"]) < args.target_slots:
            raise RuntimeError(
                "Unexpected /admin/slots total below generated set: "
                f"total={payload['total']}, expected>={args.target_slots}",
            )

    def _validate_non_empty(payload: dict[str, object]) -> None:
        if not payload:
            raise RuntimeError("Endpoint returned empty object")

    benchmarks = [
        _benchmark(
            name="admin_teachers",
            path=teachers_path,
            base_url=base_url,
            access_token=admin_token,
            warmup=args.warmup,
            iterations=args.iterations,
            validator=_validate_teachers,
        ),
        _benchmark(
            name="admin_slots",
            path=slots_path,
            base_url=base_url,
            access_token=admin_token,
            warmup=args.warmup,
            iterations=args.iterations,
            validator=_validate_slots,
        ),
        _benchmark(
            name="admin_kpi_overview",
            path=overview_path,
            base_url=base_url,
            access_token=admin_token,
            warmup=args.warmup,
            iterations=args.iterations,
            validator=_validate_non_empty,
        ),
        _benchmark(
            name="admin_kpi_sales",
            path=sales_path,
            base_url=base_url,
            access_token=admin_token,
            warmup=args.warmup,
            iterations=args.iterations,
            validator=_validate_non_empty,
        ),
    ]

    report_payload: dict[str, object] = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "base_url": base_url,
        "config": {
            "warmup": args.warmup,
            "iterations": args.iterations,
            "target_slots": args.target_slots,
            "teachers_count": args.teachers_count,
        },
        "dataset": {
            "teacher_query_token": teacher_query_token,
            "heavy_teacher_id": heavy_teacher_id,
            "teachers_created": args.teachers_count,
            "slots_created": slots_created,
            "slot_date_from": date_from.isoformat(),
            "slot_date_to": date_to.isoformat(),
        },
        "benchmarks": [asdict(item) for item in benchmarks],
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    _write_report_json(output_json, report_payload)
    _write_report_md(output_md, report_payload)

    print("Admin performance baseline completed.")
    print(f"  report_json={output_json}")
    print(f"  report_md={output_md}")
    for entry in benchmarks:
        print(
            "  "
            f"{entry.endpoint}: avg={entry.avg_ms:.2f}ms "
            f"p95={entry.p95_ms:.2f}ms max={entry.max_ms:.2f}ms",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
