#!/usr/bin/env python3
"""Fire synthetic alerts and verify Alertmanager delivery to real integrations."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

SUPPORTED_INTEGRATIONS = ("slack", "pagerduty", "email")


def _http_json(url: str, method: str = "GET", payload: Any | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - operator-provided URL
            raw = response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - covered in integration runbook usage
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {detail}") from exc
    except URLError as exc:  # pragma: no cover - covered in integration runbook usage
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc
    if not raw.strip():
        return None
    return json.loads(raw)


def _http_text(url: str) -> str:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - operator-provided URL
            return response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - covered in integration runbook usage
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} failed: HTTP {exc.code} {detail}") from exc
    except URLError as exc:  # pragma: no cover - covered in integration runbook usage
        raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc


def _parse_integrations(config_original: str) -> list[str]:
    configured: list[str] = []
    mapping = {
        "slack": "slack_configs:",
        "pagerduty": "pagerduty_configs:",
        "email": "email_configs:",
    }
    for integration, marker in mapping.items():
        if marker in config_original:
            configured.append(integration)
    return configured


def _parse_metric_value(metrics_text: str, metric_name: str, integration: str) -> float:
    pattern = re.compile(
        rf"^{re.escape(metric_name)}\{{([^}}]+)\}}\s+([-+0-9.eE]+)$",
        flags=re.MULTILINE,
    )
    for labels_blob, value in pattern.findall(metrics_text):
        labels = {}
        for item in labels_blob.split(","):
            if "=" not in item:
                continue
            key, raw = item.split("=", 1)
            labels[key.strip()] = raw.strip().strip('"')
        if labels.get("integration") == integration:
            return float(value)
    return 0.0


def _snapshot(base_url: str, integrations: list[str]) -> dict[str, dict[str, float]]:
    metrics = _http_text(f"{base_url}/metrics")
    return {
        integration: {
            "notifications_total": _parse_metric_value(
                metrics,
                "alertmanager_notifications_total",
                integration,
            ),
            "requests_failed_total": _parse_metric_value(
                metrics,
                "alertmanager_notification_requests_failed_total",
                integration,
            ),
        }
        for integration in integrations
    }


def _post_synthetic_alerts(base_url: str, duration_minutes: int, run_id: str) -> None:
    starts_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ends_at = (datetime.now(UTC) + timedelta(minutes=duration_minutes)).isoformat().replace(
        "+00:00",
        "Z",
    )
    payload = [
        {
            "labels": {
                "alertname": "GuitarOnlineSyntheticWarning",
                "severity": "warning",
                "source": "synthetic",
                "run_id": run_id,
            },
            "annotations": {
                "summary": "Synthetic warning routing test",
                "description": "Synthetic warning alert for delivery verification.",
            },
            "startsAt": starts_at,
            "endsAt": ends_at,
        },
        {
            "labels": {
                "alertname": "GuitarOnlineSyntheticCritical",
                "severity": "critical",
                "source": "synthetic",
                "run_id": run_id,
            },
            "annotations": {
                "summary": "Synthetic critical routing test",
                "description": "Synthetic critical alert for delivery verification.",
            },
            "startsAt": starts_at,
            "endsAt": ends_at,
        },
    ]
    _http_json(f"{base_url}/api/v2/alerts", method="POST", payload=payload)


def _alerts_visible(base_url: str, run_id: str) -> bool:
    alerts = _http_json(f"{base_url}/api/v2/alerts")
    severities = {
        alert.get("labels", {}).get("severity")
        for alert in alerts
        if alert.get("labels", {}).get("run_id") == run_id
    }
    return {"warning", "critical"}.issubset(severities)


def _delta(
    before: dict[str, dict[str, float]],
    after: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for integration in before:
        result[integration] = {
            "notifications_total": after[integration]["notifications_total"]
            - before[integration]["notifications_total"],
            "requests_failed_total": after[integration]["requests_failed_total"]
            - before[integration]["requests_failed_total"],
        }
    return result


def _validation_succeeded(
    deltas: dict[str, dict[str, float]],
    require_all_integrations: bool,
) -> bool:
    def is_success(integration: str) -> bool:
        return (
            deltas[integration]["notifications_total"] > 0
            and deltas[integration]["requests_failed_total"] <= 0
        )

    if require_all_integrations:
        return all(is_success(integration) for integration in deltas)
    return any(is_success(integration) for integration in deltas)


def _parse_expected_integrations(value: str | None) -> list[str] | None:
    if value is None:
        return None
    expected = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = sorted(set(expected) - set(SUPPORTED_INTEGRATIONS))
    if invalid:
        raise ValueError(
            f"Unsupported integrations in --expect-integrations: {', '.join(invalid)}. "
            f"Supported: {', '.join(SUPPORTED_INTEGRATIONS)}"
        )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fire synthetic warning/critical alerts and verify Alertmanager delivery "
            "for Slack/PagerDuty/Email via metrics deltas."
        )
    )
    parser.add_argument(
        "--alertmanager-url",
        default="http://localhost:9093",
        help="Alertmanager base URL (default: http://localhost:9093).",
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=15,
        help="Synthetic alert lifetime in minutes (default: 15).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="How long to wait for notification metric deltas (default: 180).",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Polling interval for metrics checks (default: 5).",
    )
    parser.add_argument(
        "--expect-integrations",
        default=None,
        help=(
            "Comma-separated expected integrations (slack,pagerduty,email). "
            "By default, inferred from loaded Alertmanager config."
        ),
    )
    parser.add_argument(
        "--require-all-integrations",
        action="store_true",
        help="Require successful notification delta for every expected integration.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not submit synthetic alerts; print configured integrations and baseline metrics.",
    )
    args = parser.parse_args()

    if args.duration_minutes <= 0:
        raise ValueError("--duration-minutes must be greater than 0")
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be greater than 0")
    if args.poll_seconds <= 0:
        raise ValueError("--poll-seconds must be greater than 0")

    base_url = args.alertmanager_url.rstrip("/")
    status = _http_json(f"{base_url}/api/v2/status")
    config_original = status.get("config", {}).get("original", "")
    if not config_original:
        raise RuntimeError("Alertmanager returned empty config in /api/v2/status")

    expected = _parse_expected_integrations(args.expect_integrations)
    if expected is None:
        expected = _parse_integrations(config_original)
    if not expected:
        raise RuntimeError(
            "No real receivers detected in loaded Alertmanager config. "
            "Render and enable on-call config first."
        )

    before = _snapshot(base_url, expected)
    print("Configured integrations:", ", ".join(expected))
    print("Baseline metrics snapshot:", json.dumps(before, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("Dry-run mode: synthetic alerts were not submitted.")
        return 0

    run_id = uuid4().hex
    _post_synthetic_alerts(base_url, args.duration_minutes, run_id)
    print(f"Synthetic alerts submitted. run_id={run_id}")

    deadline = time.monotonic() + args.timeout_seconds
    last_deltas: dict[str, dict[str, float]] = {
        integration: {"notifications_total": 0.0, "requests_failed_total": 0.0}
        for integration in expected
    }
    alerts_seen = False

    while time.monotonic() < deadline:
        alerts_seen = alerts_seen or _alerts_visible(base_url, run_id)
        after = _snapshot(base_url, expected)
        deltas = _delta(before, after)
        last_deltas = deltas
        if alerts_seen and _validation_succeeded(deltas, args.require_all_integrations):
            print("Delivery verification passed.")
            print("Metric deltas:", json.dumps(deltas, indent=2, ensure_ascii=False))
            return 0
        time.sleep(args.poll_seconds)

    failure_reason = "timed out while waiting for notification metric deltas"
    if not alerts_seen:
        failure_reason = "synthetic alerts did not become visible in Alertmanager API"
    print("Delivery verification failed:", failure_reason, file=sys.stderr)
    print(f"run_id={run_id}", file=sys.stderr)
    print(
        "Last metric deltas:",
        json.dumps(last_deltas, indent=2, ensure_ascii=False),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
