"""Post-deploy smoke checks executed from the app container."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from uuid import uuid4

BASE_URL = "http://localhost:8000"


def request(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, str] | None = None,
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
    email = f"deploy-smoke-{suffix}@guitaronline.dev"
    password = "StrongPass123!"

    request(
        "/api/v1/identity/auth/register",
        method="POST",
        body={"email": email, "password": password, "timezone": "UTC", "role": "student"},
        expected=201,
    )
    login_payload = json.loads(
        request(
            "/api/v1/identity/auth/login",
            method="POST",
            body={"email": email, "password": password},
            expected=200,
        ).decode("utf-8")
    )
    request(
        "/api/v1/identity/users/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
        expected=200,
    )

    print("Smoke checks passed.")


if __name__ == "__main__":
    main()
