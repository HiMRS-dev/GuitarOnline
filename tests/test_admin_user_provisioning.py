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
        users: list[FakeUser] | None = None,
        role_names: tuple[RoleEnum, ...] = (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN),
    ) -> None:
        self.existing_user = existing_user
        self.roles = {
            role_name: FakeRole(id=uuid4(), name=role_name)
            for role_name in role_names
        }
        self.users_by_id = {user.id: user for user in (users or [])}
        self.create_calls: list[dict[str, object]] = []
        self.set_active_calls: list[dict[str, object]] = []

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

    async def list_users(
        self,
        *,
        limit: int,
        offset: int,
        role: RoleEnum | None,
        is_active: bool | None,
        q: str | None,
    ) -> tuple[list[dict[str, object]], int]:
        normalized_q = q.strip().lower() if q else None
        filtered: list[FakeUser] = list(self.users_by_id.values())

        if role is not None:
            filtered = [user for user in filtered if user.role.name == role]
        if is_active is not None:
            filtered = [user for user in filtered if user.is_active is is_active]
        if normalized_q:
            filtered = [
                user
                for user in filtered
                if normalized_q in user.email.lower()
                or (
                    user.teacher_profile is not None
                    and normalized_q in user.teacher_profile.display_name.lower()
                )
            ]

        filtered.sort(
            key=lambda item: (item.created_at.timestamp(), str(item.id)),
            reverse=True,
        )
        total = len(filtered)
        paged = filtered[offset : offset + limit]
        items = [
            {
                "user_id": user.id,
                "email": user.email,
                "timezone": user.timezone,
                "role": user.role.name,
                "is_active": user.is_active,
                "teacher_profile_display_name": (
                    user.teacher_profile.display_name if user.teacher_profile is not None else None
                ),
                "created_at_utc": user.created_at,
                "updated_at_utc": user.updated_at,
            }
            for user in paged
        ]
        return items, total

    async def get_user_by_id(
        self,
        *,
        user_id: UUID,
        lock_for_update: bool = False,
    ) -> FakeUser | None:
        _ = lock_for_update
        return self.users_by_id.get(user_id)

    async def set_user_active(self, *, user: FakeUser, is_active: bool, admin_id: UUID) -> FakeUser:
        user.is_active = is_active
        self.set_active_calls.append(
            {
                "user_id": user.id,
                "is_active": is_active,
                "admin_id": admin_id,
            },
        )
        return user


def make_actor(role: RoleEnum, *, user_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=user_id or uuid4(), role=SimpleNamespace(name=role))


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


def make_user(
    *,
    email: str,
    role: RoleEnum,
    is_active: bool = True,
    display_name: str | None = None,
) -> FakeUser:
    now = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)
    profile = (
        FakeTeacherProfile(
            id=uuid4(),
            display_name=display_name or "Teacher",
            status=TeacherStatusEnum.PENDING,
            is_approved=False,
        )
        if role == RoleEnum.TEACHER
        else None
    )
    return FakeUser(
        id=uuid4(),
        email=email,
        password_hash="hash",
        timezone="UTC",
        is_active=is_active,
        role=FakeRole(id=uuid4(), name=role),
        created_at=now,
        updated_at=now,
        teacher_profile=profile,
    )


@pytest.mark.asyncio
async def test_admin_can_list_users_with_filters() -> None:
    teacher = make_user(
        email="teacher-list@guitaronline.dev",
        role=RoleEnum.TEACHER,
        display_name="Teacher List",
    )
    student = make_user(email="student-list@guitaronline.dev", role=RoleEnum.STUDENT)
    repository = FakeAdminRepository(users=[teacher, student])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    items, total = await service.list_users(
        admin,
        limit=50,
        offset=0,
        role=RoleEnum.TEACHER,
        is_active=True,
        q="teacher-list",
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].user_id == teacher.id
    assert items[0].teacher_profile_display_name == "Teacher List"


@pytest.mark.asyncio
async def test_admin_can_activate_and_deactivate_user() -> None:
    target_user = make_user(
        email="toggle@guitaronline.dev",
        role=RoleEnum.STUDENT,
        is_active=False,
    )
    repository = FakeAdminRepository(users=[target_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    activated = await service.activate_user(admin, user_id=target_user.id)
    assert activated.is_active is True

    deactivated = await service.deactivate_user(admin, user_id=target_user.id)
    assert deactivated.is_active is False
    assert repository.set_active_calls == [
        {"user_id": target_user.id, "is_active": True, "admin_id": admin.id},
        {"user_id": target_user.id, "is_active": False, "admin_id": admin.id},
    ]


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_own_account() -> None:
    admin_user = make_user(
        email="self-admin@guitaronline.dev",
        role=RoleEnum.ADMIN,
        is_active=True,
    )
    repository = FakeAdminRepository(users=[admin_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN, user_id=admin_user.id)

    with pytest.raises(ConflictException, match="cannot deactivate own account"):
        await service.deactivate_user(admin, user_id=admin_user.id)

    assert repository.set_active_calls == []
