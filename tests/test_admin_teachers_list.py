from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import UnauthorizedException


class FakeAdminRepository:
    def __init__(self, items: list[dict], total: int) -> None:
        self.items = items
        self.total = total
        self.calls: list[dict[str, object]] = []

    async def list_teachers(
        self,
        *,
        limit: int,
        offset: int,
        status: TeacherStatusEnum | None,
        q: str | None,
        tag: str | None,
    ) -> tuple[list[dict], int]:
        self.calls.append(
            {
                "limit": limit,
                "offset": offset,
                "status": status,
                "q": q,
                "tag": tag,
            },
        )
        return self.items, self.total


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_item() -> dict:
    return {
        "teacher_id": uuid4(),
        "profile_id": uuid4(),
        "email": "teacher@example.com",
        "display_name": "Alice Blues",
        "status": TeacherStatusEnum.ACTIVE,
        "is_active": True,
        "tags": ["jazz", "fingerstyle"],
        "created_at_utc": datetime(2026, 3, 5, 10, 0, tzinfo=UTC),
        "updated_at_utc": datetime(2026, 3, 5, 10, 15, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_admin_teacher_list_returns_items_and_passes_filters() -> None:
    repository = FakeAdminRepository(items=[make_item()], total=1)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    items, total = await service.list_teachers(
        admin,
        limit=20,
        offset=0,
        status=TeacherStatusEnum.ACTIVE,
        q="alice",
        tag="jazz",
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].display_name == "Alice Blues"
    assert repository.calls == [
        {
            "limit": 20,
            "offset": 0,
            "status": TeacherStatusEnum.ACTIVE,
            "q": "alice",
            "tag": "jazz",
        },
    ]


@pytest.mark.asyncio
async def test_admin_teacher_list_requires_admin_role() -> None:
    repository = FakeAdminRepository(items=[make_item()], total=1)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.list_teachers(
            teacher,
            limit=20,
            offset=0,
            status=None,
            q=None,
            tag=None,
        )

    assert repository.calls == []
