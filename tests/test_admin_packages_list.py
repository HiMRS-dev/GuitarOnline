from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import PackageStatusEnum, RoleEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import UnauthorizedException


class FakeAdminRepository:
    def __init__(self, items: list[dict], total: int) -> None:
        self.items = items
        self.total = total
        self.calls: list[dict[str, object]] = []

    async def list_packages(
        self,
        *,
        student_id,
        status,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        self.calls.append(
            {
                "student_id": student_id,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
        )
        return self.items, self.total


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_item() -> dict:
    return {
        "package_id": uuid4(),
        "student_id": uuid4(),
        "lessons_total": 12,
        "lessons_left": 4,
        "price_amount": Decimal("149.00"),
        "price_currency": "USD",
        "expires_at_utc": datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        "status": PackageStatusEnum.ACTIVE,
        "created_at_utc": datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
        "updated_at_utc": datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_admin_packages_list_passes_filters_and_serializes_rows() -> None:
    item = make_item()
    repository = FakeAdminRepository(items=[item], total=1)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    student_id = uuid4()

    items, total = await service.list_packages(
        admin,
        student_id=student_id,
        status=PackageStatusEnum.DEPLETED,
        limit=20,
        offset=5,
    )

    assert total == 1
    assert items[0].package_id == item["package_id"]
    assert items[0].status == PackageStatusEnum.ACTIVE
    assert items[0].price_amount == Decimal("149.00")
    assert items[0].price_currency == "USD"
    assert repository.calls == [
        {
            "student_id": student_id,
            "status": PackageStatusEnum.DEPLETED,
            "limit": 20,
            "offset": 5,
        },
    ]


@pytest.mark.asyncio
async def test_admin_packages_list_without_filters() -> None:
    repository = FakeAdminRepository(items=[make_item()], total=1)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    items, total = await service.list_packages(
        admin,
        student_id=None,
        status=None,
        limit=10,
        offset=0,
    )

    assert total == 1
    assert len(items) == 1
    assert repository.calls == [
        {
            "student_id": None,
            "status": None,
            "limit": 10,
            "offset": 0,
        },
    ]


@pytest.mark.asyncio
async def test_admin_packages_list_requires_admin_role() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.list_packages(
            teacher,
            student_id=None,
            status=None,
            limit=20,
            offset=0,
        )

    assert repository.calls == []
