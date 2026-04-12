from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.enums import RoleEnum
from app.modules.identity.router import router
from app.modules.identity.service import get_current_user, get_identity_service


class FakeIdentityService:
    def __init__(self) -> None:
        self.updated_payloads: list[object] = []

    async def update_current_user_profile(self, current_user, payload):
        self.updated_payloads.append(payload)
        return SimpleNamespace(
            id=current_user.id,
            email=current_user.email,
            full_name=payload.full_name,
            timezone=current_user.timezone,
            is_active=current_user.is_active,
            role=current_user.role,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        )


def _build_current_user():
    return SimpleNamespace(
        id=uuid4(),
        email="student-test@guitaronline.dev",
        full_name="Initial Name",
        timezone="UTC",
        is_active=True,
        role=SimpleNamespace(id=uuid4(), name=RoleEnum.STUDENT),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _build_client(service: FakeIdentityService) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_identity_service] = lambda: service
    app.dependency_overrides[get_current_user] = _build_current_user
    return TestClient(app)


def test_patch_me_updates_full_name() -> None:
    service = FakeIdentityService()
    client = _build_client(service)

    response = client.patch(
        "/api/v1/identity/users/me",
        json={"full_name": "Updated Name"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"
    assert len(service.updated_payloads) == 1
    assert service.updated_payloads[0].full_name == "Updated Name"


def test_patch_me_rejects_extra_fields() -> None:
    service = FakeIdentityService()
    client = _build_client(service)

    response = client.patch(
        "/api/v1/identity/users/me",
        json={"full_name": "Updated Name", "role": "admin"},
    )

    assert response.status_code == 422
