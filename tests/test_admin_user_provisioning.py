from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import RoleEnum, TeacherStatusEnum
from app.core.security import verify_password
from app.modules.admin.schemas import (
    AdminProvisionTeacherProfileRequest,
    AdminUserProvisionRequest,
)
from app.modules.admin.service import AdminService
from app.shared.exceptions import ConflictException, NotFoundException, UnauthorizedException


@dataclass
class FakeRole:
    id: UUID
    name: RoleEnum


@dataclass
class FakeTeacherProfile:
    id: UUID
    display_name: str
    status: TeacherStatusEnum
    is_approved: bool


@dataclass
class FakeUser:
    id: UUID
    email: str
    password_hash: str
    timezone: str
    is_active: bool
    role: FakeRole
    created_at: datetime
    updated_at: datetime
    teacher_profile: FakeTeacherProfile | None = None


class FakeAdminRepository:
    def __init__(
        self,
        *,
        existing_user: FakeUser | None = None,
        role_names: tuple[RoleEnum, ...] = (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN),
    ) -> None:
        self.existing_user = existing_user
        self.roles = {
            role_name: FakeRole(id=uuid4(), name=role_name)
            for role_name in role_names
        }
        self.create_calls: list[dict[str, object]] = []

    async def get_user_by_email(self, email: str) -> FakeUser | None:
        if self.existing_user is None:
            return None
        return self.existing_user if self.existing_user.email == email else None

    async def get_role_by_name(self, role_name: RoleEnum) -> FakeRole | None:
        return self.roles.get(role_name)

    async def create_provisioned_user(
        self,
        *,
        email: str,
        password_hash: str,
        timezone: str,
        role_id: UUID,
        role_name: RoleEnum,
        teacher_profile: dict[str, object] | None,
        admin_id: UUID,
    ) -> FakeUser:
        self.create_calls.append(
            {
                "email": email,
                "password_hash": password_hash,
                "timezone": timezone,
                "role_id": role_id,
                "role_name": role_name,
                "teacher_profile": teacher_profile,
                "admin_id": admin_id,
            },
        )
        role = self.roles[role_name]
        profile_obj: FakeTeacherProfile | None = None
        if role_name == RoleEnum.TEACHER and teacher_profile is not None:
            profile_obj = FakeTeacherProfile(
                id=uuid4(),
                display_name=str(teacher_profile["display_name"]),
                status=TeacherStatusEnum.PENDING,
                is_approved=False,
            )

        now = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
        return FakeUser(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            timezone=timezone,
            is_active=True,
            role=role,
            created_at=now,
            updated_at=now,
            teacher_profile=profile_obj,
        )


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


@pytest.mark.asyncio
async def test_admin_can_provision_teacher_with_pending_profile() -> None:
    repository = FakeAdminRepository()
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    payload = AdminUserProvisionRequest(
        email="provision-teacher@guitaronline.dev",
        password="StrongPass123!",
        timezone="UTC",
        role=RoleEnum.TEACHER,
        teacher_profile=AdminProvisionTeacherProfileRequest(
            display_name="Provisioned Teacher",
            bio="Jazz and blues",
            experience_years=9,
        ),
    )

    result = await service.provision_user(admin, payload=payload)

    assert result.role == RoleEnum.TEACHER
    assert result.teacher_profile is not None
    assert result.teacher_profile.display_name == "Provisioned Teacher"
    assert result.teacher_profile.status == TeacherStatusEnum.PENDING
    assert result.teacher_profile.verified is False
    assert len(repository.create_calls) == 1
    call = repository.create_calls[0]
    assert call["role_name"] == RoleEnum.TEACHER
    assert call["teacher_profile"] is not None
    assert verify_password(payload.password, str(call["password_hash"]))
    assert call["password_hash"] != payload.password


@pytest.mark.asyncio
async def test_admin_can_provision_admin_without_teacher_profile() -> None:
    repository = FakeAdminRepository()
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    payload = AdminUserProvisionRequest(
        email="provision-admin@guitaronline.dev",
        password="StrongPass123!",
        timezone="Europe/Moscow",
        role=RoleEnum.ADMIN,
    )

    result = await service.provision_user(admin, payload=payload)

    assert result.role == RoleEnum.ADMIN
    assert result.teacher_profile is None
    assert repository.create_calls[0]["role_name"] == RoleEnum.ADMIN
    assert repository.create_calls[0]["teacher_profile"] is None


@pytest.mark.asyncio
async def test_provision_user_requires_admin_role() -> None:
    repository = FakeAdminRepository()
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)
    payload = AdminUserProvisionRequest(
        email="forbidden@guitaronline.dev",
        password="StrongPass123!",
        timezone="UTC",
        role=RoleEnum.ADMIN,
    )

    with pytest.raises(UnauthorizedException, match="Only admin can provision users"):
        await service.provision_user(teacher, payload=payload)

    assert repository.create_calls == []


@pytest.mark.asyncio
async def test_provision_user_rejects_duplicate_email() -> None:
    existing = FakeUser(
        id=uuid4(),
        email="duplicate@guitaronline.dev",
        password_hash="hash",
        timezone="UTC",
        is_active=True,
        role=FakeRole(id=uuid4(), name=RoleEnum.STUDENT),
        created_at=datetime(2026, 3, 10, 11, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 10, 11, 0, tzinfo=UTC),
    )
    repository = FakeAdminRepository(existing_user=existing)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    payload = AdminUserProvisionRequest(
        email="duplicate@guitaronline.dev",
        password="StrongPass123!",
        timezone="UTC",
        role=RoleEnum.ADMIN,
    )

    with pytest.raises(ConflictException, match="already exists"):
        await service.provision_user(admin, payload=payload)

    assert repository.create_calls == []


@pytest.mark.asyncio
async def test_provision_user_fails_when_target_role_is_missing() -> None:
    repository = FakeAdminRepository(role_names=(RoleEnum.STUDENT, RoleEnum.TEACHER))
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    payload = AdminUserProvisionRequest(
        email="missing-role@guitaronline.dev",
        password="StrongPass123!",
        timezone="UTC",
        role=RoleEnum.ADMIN,
    )

    with pytest.raises(NotFoundException, match="Role not found"):
        await service.provision_user(admin, payload=payload)

    assert repository.create_calls == []


def test_provision_request_rejects_student_role() -> None:
    with pytest.raises(ValidationError, match="teacher/admin"):
        AdminUserProvisionRequest(
            email="student@guitaronline.dev",
            password="StrongPass123!",
            timezone="UTC",
            role=RoleEnum.STUDENT,
        )
