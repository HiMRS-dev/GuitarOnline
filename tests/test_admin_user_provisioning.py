from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.admin.schemas import AdminUserRoleUpdateRequest
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
        users: list[FakeUser] | None = None,
        role_names: tuple[RoleEnum, ...] = (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN),
    ) -> None:
        self.roles = {
            role_name: FakeRole(id=uuid4(), name=role_name)
            for role_name in role_names
        }
        self.users_by_id = {user.id: user for user in (users or [])}
        self.set_role_calls: list[dict[str, object]] = []
        self.set_active_calls: list[dict[str, object]] = []

    async def get_role_by_name(self, role_name: RoleEnum) -> FakeRole | None:
        return self.roles.get(role_name)

    async def set_user_role(
        self,
        *,
        user: FakeUser,
        role: FakeRole,
        admin_id: UUID,
    ) -> FakeUser:
        previous_role = user.role.name
        user.role = role

        profile = user.teacher_profile
        teacher_profile_created = False
        if role.name == RoleEnum.TEACHER:
            if profile is None:
                profile = FakeTeacherProfile(
                    id=uuid4(),
                    display_name=user.email.split("@", 1)[0],
                    status=TeacherStatusEnum.ACTIVE,
                )
                user.teacher_profile = profile
                teacher_profile_created = True
            else:
                profile.status = TeacherStatusEnum.ACTIVE
        elif profile is not None:
            profile.status = TeacherStatusEnum.DISABLED

        self.set_role_calls.append(
            {
                "user_id": user.id,
                "from_role": previous_role,
                "to_role": role.name,
                "admin_id": admin_id,
                "teacher_profile_created": teacher_profile_created,
            },
        )
        return user

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
                    user.teacher_profile.display_name
                    if user.role.name == RoleEnum.TEACHER and user.teacher_profile is not None
                    else None
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


def make_user(
    *,
    email: str,
    role: RoleEnum,
    is_active: bool = True,
    display_name: str | None = None,
    teacher_status: TeacherStatusEnum = TeacherStatusEnum.ACTIVE,
) -> FakeUser:
    now = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)
    profile = (
        FakeTeacherProfile(
            id=uuid4(),
            display_name=display_name or "Teacher",
            status=teacher_status,
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
async def test_admin_can_promote_student_to_teacher_with_active_profile() -> None:
    target_user = make_user(email="student@guitaronline.dev", role=RoleEnum.STUDENT)
    repository = FakeAdminRepository(users=[target_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.update_user_role(
        admin,
        user_id=target_user.id,
        payload=AdminUserRoleUpdateRequest(role=RoleEnum.TEACHER),
    )

    assert result.role == RoleEnum.TEACHER
    assert result.teacher_profile_display_name == "student"
    assert target_user.teacher_profile is not None
    assert target_user.teacher_profile.status == TeacherStatusEnum.ACTIVE
    assert repository.set_role_calls == [
        {
            "user_id": target_user.id,
            "from_role": RoleEnum.STUDENT,
            "to_role": RoleEnum.TEACHER,
            "admin_id": admin.id,
            "teacher_profile_created": True,
        },
    ]


@pytest.mark.asyncio
async def test_admin_can_promote_student_to_admin_without_teacher_profile() -> None:
    target_user = make_user(email="student-admin@guitaronline.dev", role=RoleEnum.STUDENT)
    repository = FakeAdminRepository(users=[target_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.update_user_role(
        admin,
        user_id=target_user.id,
        payload=AdminUserRoleUpdateRequest(role=RoleEnum.ADMIN),
    )

    assert result.role == RoleEnum.ADMIN
    assert result.teacher_profile_display_name is None
    assert target_user.teacher_profile is None
    assert repository.set_role_calls[0]["to_role"] == RoleEnum.ADMIN


@pytest.mark.asyncio
async def test_admin_can_demote_teacher_and_hide_teacher_profile_from_user_list() -> None:
    target_user = make_user(
        email="teacher@guitaronline.dev",
        role=RoleEnum.TEACHER,
        display_name="Teacher Name",
        teacher_status=TeacherStatusEnum.ACTIVE,
    )
    repository = FakeAdminRepository(users=[target_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.update_user_role(
        admin,
        user_id=target_user.id,
        payload=AdminUserRoleUpdateRequest(role=RoleEnum.STUDENT),
    )

    assert result.role == RoleEnum.STUDENT
    assert result.teacher_profile_display_name is None
    assert target_user.teacher_profile is not None
    assert target_user.teacher_profile.status == TeacherStatusEnum.DISABLED


@pytest.mark.asyncio
async def test_update_user_role_requires_admin_role() -> None:
    target_user = make_user(email="target@guitaronline.dev", role=RoleEnum.STUDENT)
    repository = FakeAdminRepository(users=[target_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException, match="Only admin can change user roles"):
        await service.update_user_role(
            teacher,
            user_id=target_user.id,
            payload=AdminUserRoleUpdateRequest(role=RoleEnum.ADMIN),
        )

    assert repository.set_role_calls == []


@pytest.mark.asyncio
async def test_update_user_role_fails_when_target_role_is_missing() -> None:
    target_user = make_user(email="missing-role@guitaronline.dev", role=RoleEnum.STUDENT)
    repository = FakeAdminRepository(
        users=[target_user],
        role_names=(RoleEnum.STUDENT, RoleEnum.TEACHER),
    )
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(NotFoundException, match="Role not found"):
        await service.update_user_role(
            admin,
            user_id=target_user.id,
            payload=AdminUserRoleUpdateRequest(role=RoleEnum.ADMIN),
        )

    assert repository.set_role_calls == []


@pytest.mark.asyncio
async def test_admin_cannot_change_own_role() -> None:
    admin_user = make_user(email="self-admin@guitaronline.dev", role=RoleEnum.ADMIN)
    repository = FakeAdminRepository(users=[admin_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN, user_id=admin_user.id)

    with pytest.raises(ConflictException, match="cannot change own role"):
        await service.update_user_role(
            admin,
            user_id=admin_user.id,
            payload=AdminUserRoleUpdateRequest(role=RoleEnum.STUDENT),
        )

    assert repository.set_role_calls == []


@pytest.mark.asyncio
async def test_update_user_role_with_same_role_is_noop() -> None:
    target_user = make_user(email="admin@guitaronline.dev", role=RoleEnum.ADMIN)
    repository = FakeAdminRepository(users=[target_user])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.update_user_role(
        admin,
        user_id=target_user.id,
        payload=AdminUserRoleUpdateRequest(role=RoleEnum.ADMIN),
    )

    assert result.role == RoleEnum.ADMIN
    assert repository.set_role_calls == []


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
