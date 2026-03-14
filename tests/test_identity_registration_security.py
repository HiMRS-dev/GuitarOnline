from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import app.modules.identity.service as identity_service_module
from app.core.enums import RoleEnum
from app.modules.identity.schemas import UserCreate
from app.modules.identity.service import IdentityService
from app.shared.exceptions import UnauthorizedException


@dataclass
class FakeRole:
    id: UUID
    name: RoleEnum


@dataclass
class FakeUser:
    id: UUID
    email: str
    password_hash: str
    timezone: str
    role: FakeRole
    is_active: bool = True


class FakeIdentityRepository:
    def __init__(self) -> None:
        self.roles = {
            RoleEnum.STUDENT: FakeRole(id=uuid4(), name=RoleEnum.STUDENT),
            RoleEnum.TEACHER: FakeRole(id=uuid4(), name=RoleEnum.TEACHER),
            RoleEnum.ADMIN: FakeRole(id=uuid4(), name=RoleEnum.ADMIN),
        }
        self.users_by_email: dict[str, FakeUser] = {}

    async def get_user_by_email(self, email: str) -> FakeUser | None:
        return self.users_by_email.get(email)

    async def get_role_by_name(self, role_name: RoleEnum) -> FakeRole | None:
        return self.roles.get(role_name)

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        timezone: str,
        role_id: UUID,
    ) -> FakeUser:
        role = next(role for role in self.roles.values() if role.id == role_id)
        user = FakeUser(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            timezone=timezone,
            role=role,
        )
        self.users_by_email[email] = user
        return user


@pytest.mark.asyncio
async def test_register_rejects_when_student_self_registration_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        identity_service_module,
        "get_settings",
        lambda: SimpleNamespace(auth_self_registration_enabled=False),
    )
    service = IdentityService(FakeIdentityRepository())  # type: ignore[arg-type]

    with pytest.raises(UnauthorizedException, match="Self-registration is disabled"):
        await service.register(
            UserCreate(
                email="student-register-disabled@guitaronline.dev",
                password="StrongPass123!",
                timezone="UTC",
            ),
        )


@pytest.mark.asyncio
async def test_register_always_creates_student_when_self_registration_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        identity_service_module,
        "get_settings",
        lambda: SimpleNamespace(auth_self_registration_enabled=True),
    )
    service = IdentityService(FakeIdentityRepository())  # type: ignore[arg-type]

    user = await service.register(
        UserCreate(
            email="student-default@guitaronline.dev",
            password="StrongPass123!",
            timezone="UTC",
        ),
    )

    assert user.role.name == RoleEnum.STUDENT


def test_user_create_rejects_public_role_field() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        UserCreate(
            email="role-field@guitaronline.dev",
            password="StrongPass123!",
            timezone="UTC",
            role=RoleEnum.ADMIN,
        )
