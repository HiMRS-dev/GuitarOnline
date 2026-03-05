from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import NotFoundException, UnauthorizedException


class FakeAdminRepository:
    def __init__(self, item: dict | None) -> None:
        self.item = item
        self.calls: list[dict[str, object]] = []

    async def verify_teacher(self, *, teacher_id, admin_id) -> dict | None:
        self.calls.append(
            {
                "method": "verify_teacher",
                "teacher_id": teacher_id,
                "admin_id": admin_id,
            },
        )
        return self.item

    async def disable_teacher(self, *, teacher_id, admin_id) -> dict | None:
        self.calls.append(
            {
                "method": "disable_teacher",
                "teacher_id": teacher_id,
                "admin_id": admin_id,
            },
        )
        return self.item


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_item(*, status: TeacherStatusEnum, verified: bool, is_active: bool) -> dict:
    return {
        "teacher_id": uuid4(),
        "profile_id": uuid4(),
        "email": "teacher@example.com",
        "display_name": "Alice Blues",
        "bio": "Fingerstyle teacher",
        "experience_years": 7,
        "status": status,
        "verified": verified,
        "is_active": is_active,
        "tags": ["jazz", "fingerstyle"],
        "created_at_utc": datetime(2026, 3, 5, 12, 0, tzinfo=UTC),
        "updated_at_utc": datetime(2026, 3, 5, 12, 30, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_admin_verify_teacher_returns_updated_detail() -> None:
    item = make_item(status=TeacherStatusEnum.VERIFIED, verified=True, is_active=True)
    repository = FakeAdminRepository(item=item)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.verify_teacher(admin, teacher_id=item["teacher_id"])

    assert result.teacher_id == item["teacher_id"]
    assert result.status == TeacherStatusEnum.VERIFIED
    assert result.verified is True
    assert repository.calls == [
        {
            "method": "verify_teacher",
            "teacher_id": item["teacher_id"],
            "admin_id": admin.id,
        },
    ]


@pytest.mark.asyncio
async def test_admin_disable_teacher_returns_updated_detail() -> None:
    item = make_item(status=TeacherStatusEnum.DISABLED, verified=False, is_active=False)
    repository = FakeAdminRepository(item=item)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.disable_teacher(admin, teacher_id=item["teacher_id"])

    assert result.teacher_id == item["teacher_id"]
    assert result.status == TeacherStatusEnum.DISABLED
    assert result.verified is False
    assert result.is_active is False
    assert repository.calls == [
        {
            "method": "disable_teacher",
            "teacher_id": item["teacher_id"],
            "admin_id": admin.id,
        },
    ]


@pytest.mark.asyncio
async def test_admin_verify_teacher_requires_admin_role() -> None:
    item = make_item(status=TeacherStatusEnum.VERIFIED, verified=True, is_active=True)
    repository = FakeAdminRepository(item=item)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.verify_teacher(teacher, teacher_id=item["teacher_id"])

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_disable_teacher_requires_admin_role() -> None:
    item = make_item(status=TeacherStatusEnum.DISABLED, verified=False, is_active=False)
    repository = FakeAdminRepository(item=item)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.disable_teacher(student, teacher_id=item["teacher_id"])

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_verify_teacher_returns_not_found_when_profile_missing() -> None:
    teacher_id = uuid4()
    repository = FakeAdminRepository(item=None)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(NotFoundException):
        await service.verify_teacher(admin, teacher_id=teacher_id)

    assert repository.calls == [
        {
            "method": "verify_teacher",
            "teacher_id": teacher_id,
            "admin_id": admin.id,
        },
    ]


@pytest.mark.asyncio
async def test_admin_disable_teacher_returns_not_found_when_profile_missing() -> None:
    teacher_id = uuid4()
    repository = FakeAdminRepository(item=None)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(NotFoundException):
        await service.disable_teacher(admin, teacher_id=teacher_id)

    assert repository.calls == [
        {
            "method": "disable_teacher",
            "teacher_id": teacher_id,
            "admin_id": admin.id,
        },
    ]
