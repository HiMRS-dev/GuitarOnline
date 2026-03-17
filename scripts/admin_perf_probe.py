#!/usr/bin/env python3
"""Probe admin endpoint latency on an existing dataset."""

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
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

DEFAULT_PASSWORD = "StrongPass123!"


def _guard_non_test_execution(*, base_url: str, allow_non_test: bool) -> None:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env in {"test", "testing"} or allow_non_test:
        return
    raise RuntimeError(
        "Refusing to run admin perf probe outside APP_ENV=test "
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
    max_attempts: int = 8,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe admin endpoint latency on existing data.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--teacher-query-token", required=True)
    parser.add_argument("--heavy-teacher-id", required=True)
    parser.add_argument("--slot-from-utc", required=True)
    parser.add_argument("--slot-to-utc", required=True)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument(
        "--allow-non-test",
        action="store_true",
        help="Allow execution when APP_ENV is not test.",
    )
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    if args.warmup < 0:
        raise RuntimeError("--warmup must be >= 0")
    if args.iterations <= 0:
        raise RuntimeError("--iterations must be > 0")

    base_url = args.base_url.rstrip("/")
    _guard_non_test_execution(base_url=base_url, allow_non_test=args.allow_non_test)

    suffix = uuid4().hex[:10]
    admin_email = f"perf-probe-admin-{suffix}@guitaronline.dev"
    shared_credential = DEFAULT_PASSWORD

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

    teachers_path = "/api/v1/admin/teachers?" + urlencode(
        {"q": args.teacher_query_token, "limit": 100, "offset": 0},
    )
    slots_path = "/api/v1/admin/slots?" + urlencode(
        {
            "teacher_id": args.heavy_teacher_id,
            "from_utc": args.slot_from_utc,
            "to_utc": args.slot_to_utc,
            "limit": 100,
            "offset": 0,
        },
    )
    overview_path = "/api/v1/admin/kpi/overview"
    sales_path = "/api/v1/admin/kpi/sales?" + urlencode(
        {
            "from_utc": "2025-09-07T08:54:33+00:00",
            "to_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
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
            validator=_validate_non_empty,
        ),
        _benchmark(
            name="admin_slots",
            path=slots_path,
            base_url=base_url,
            access_token=admin_token,
            warmup=args.warmup,
            iterations=args.iterations,
            validator=_validate_non_empty,
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

    payload = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "base_url": base_url,
        "config": {
            "warmup": args.warmup,
            "iterations": args.iterations,
            "teacher_query_token": args.teacher_query_token,
            "heavy_teacher_id": args.heavy_teacher_id,
            "slot_from_utc": args.slot_from_utc,
            "slot_to_utc": args.slot_to_utc,
        },
        "benchmarks": [asdict(item) for item in benchmarks],
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Admin perf probe completed.")
    print(f"  report_json={output_path}")
    for entry in benchmarks:
        print(
            "  "
            f"{entry.endpoint}: avg={entry.avg_ms:.2f}ms "
            f"p95={entry.p95_ms:.2f}ms max={entry.max_ms:.2f}ms",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
