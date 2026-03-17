"""Shared helpers for reusable smoke-pool integration accounts."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx

RoleName = Literal["admin", "teacher", "student", "student_two"]

INTEGRATION_DB_DSN = os.getenv(
    "INTEGRATION_DB_DSN",
    "postgresql://postgres:postgres@localhost:15432/guitaronline_test",
)
TEST_SMOKE_POOL_PASSWORD = os.getenv("TEST_SMOKE_POOL_PASSWORD", "StrongPass123!").strip()
_REPO_ROOT = Path(__file__).resolve().parents[1]
_RESET_SCRIPT = _REPO_ROOT / "scripts" / "reset_test_smoke_pool.py"
_SMOKE_EMAILS: dict[RoleName, str] = {
    "admin": os.getenv("TEST_SMOKE_ADMIN_EMAIL", "smoke-admin-1@guitaronline.dev").strip(),
    "teacher": os.getenv("TEST_SMOKE_TEACHER_EMAIL", "smoke-teacher-1@guitaronline.dev").strip(),
    "student": os.getenv("TEST_SMOKE_STUDENT_EMAIL", "smoke-student-1@guitaronline.dev").strip(),
    "student_two": os.getenv(
        "TEST_SMOKE_STUDENT_TWO_EMAIL",
        "smoke-student-2@guitaronline.dev",
    ).strip(),
}
_PORTAL_SESSION_CACHE: dict[tuple[str, RoleName], PortalAuthSession] = {}


@dataclass(slots=True)
class AuthUser:
    id: UUID
    access_token: str


@dataclass(slots=True)
class AuthUsers:
    admin: AuthUser
    teacher: AuthUser
    student: AuthUser
    student_two: AuthUser


@dataclass(slots=True)
class PortalAuthSession:
    user_id: UUID
    access_token: str
    refresh_token: str


def _assert_status(response: httpx.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"{response.request.method} {response.request.url} -> "
        f"{response.status_code}, body={response.text}"
    )


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _async_database_url() -> str:
    if INTEGRATION_DB_DSN.startswith("postgresql+asyncpg://"):
        return INTEGRATION_DB_DSN
    if INTEGRATION_DB_DSN.startswith("postgresql://"):
        return INTEGRATION_DB_DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
    if INTEGRATION_DB_DSN.startswith("postgres://"):
        return INTEGRATION_DB_DSN.replace("postgres://", "postgresql+asyncpg://", 1)
    raise AssertionError(
        f"Unsupported integration DB DSN for smoke-pool reset: {INTEGRATION_DB_DSN}",
    )


def reset_test_smoke_pool() -> None:
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["DATABASE_URL"] = _async_database_url()
    env["DEBUG"] = "false"

    completed = subprocess.run(
        [sys.executable, str(_RESET_SCRIPT)],
        capture_output=True,
        check=False,
        cwd=_REPO_ROOT,
        env=env,
        text=True,
    )
    if completed.returncode == 0:
        return

    output = "\n".join(
        chunk for chunk in (completed.stdout.strip(), completed.stderr.strip()) if chunk
    )
    raise AssertionError(
        "reset_test_smoke_pool.py failed for the isolated test contour.\n"
        f"Command: {sys.executable} {_RESET_SCRIPT}\n"
        f"Output:\n{output or '(no output)'}",
    )


async def login_smoke_auth_user(client: httpx.AsyncClient, *, role: RoleName) -> AuthUser:
    session = await login_smoke_portal_session(client, role=role)
    return AuthUser(id=session.user_id, access_token=session.access_token)


async def login_smoke_auth_users(client: httpx.AsyncClient) -> AuthUsers:
    return AuthUsers(
        admin=await login_smoke_auth_user(client, role="admin"),
        teacher=await login_smoke_auth_user(client, role="teacher"),
        student=await login_smoke_auth_user(client, role="student"),
        student_two=await login_smoke_auth_user(client, role="student_two"),
    )


async def login_smoke_portal_session(
    client: httpx.AsyncClient,
    *,
    role: RoleName,
) -> PortalAuthSession:
    cache_key = (str(client.base_url).rstrip("/"), role)
    cached_session = _PORTAL_SESSION_CACHE.get(cache_key)
    if cached_session is not None:
        me_response = await client.get(
            "/identity/users/me",
            headers=_auth_headers(cached_session.access_token),
        )
        if me_response.status_code == 200:
            return cached_session

    login_response = await client.post(
        "/identity/auth/login",
        json={
            "email": _SMOKE_EMAILS[role],
            "password": TEST_SMOKE_POOL_PASSWORD,
        },
    )
    _assert_status(login_response, 200)
    token_pair = login_response.json()

    me_response = await client.get(
        "/identity/users/me",
        headers=_auth_headers(token_pair["access_token"]),
    )
    _assert_status(me_response, 200)
    session = PortalAuthSession(
        user_id=UUID(me_response.json()["id"]),
        access_token=token_pair["access_token"],
        refresh_token=token_pair["refresh_token"],
    )
    _PORTAL_SESSION_CACHE[cache_key] = session
    return session
