from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum, SlotStatusEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import ConflictException, NotFoundException, UnauthorizedException


@dataclass(slots=True)
class FakeSlot:
    id: UUID
    teacher_id: UUID
    created_by_admin_id: UUID
    start_at: datetime
    end_at: datetime
    status: SlotStatusEnum


class FakeAdminRepository:
    def __init__(self, slot: FakeSlot | None, has_bookings: bool) -> None:
        self.slot = slot
        self.has_bookings = has_bookings
        self.calls: list[dict[str, object]] = []

    async def get_slot_by_id(self, slot_id: UUID) -> FakeSlot | None:
        self.calls.append({"method": "get_slot_by_id", "slot_id": slot_id})
        if self.slot is None:
            return None
        if self.slot.id != slot_id:
            return None
        return self.slot

    async def slot_has_bookings(self, slot_id: UUID) -> bool:
        self.calls.append({"method": "slot_has_bookings", "slot_id": slot_id})
        return self.has_bookings

    async def delete_slot(self, *, slot: FakeSlot, admin_id: UUID) -> None:
        self.calls.append(
            {
                "method": "delete_slot",
                "slot_id": slot.id,
                "admin_id": admin_id,
            },
        )


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_slot() -> FakeSlot:
    return FakeSlot(
        id=uuid4(),
        teacher_id=uuid4(),
        created_by_admin_id=uuid4(),
        start_at=datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 10, 11, 0, tzinfo=UTC),
        status=SlotStatusEnum.OPEN,
    )


@pytest.mark.asyncio
async def test_admin_delete_slot_succeeds_without_related_bookings() -> None:
    slot = make_slot()
    repository = FakeAdminRepository(slot=slot, has_bookings=False)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    await service.delete_slot(admin, slot_id=slot.id)

    assert repository.calls == [
        {"method": "get_slot_by_id", "slot_id": slot.id},
        {"method": "slot_has_bookings", "slot_id": slot.id},
        {
            "method": "delete_slot",
            "slot_id": slot.id,
            "admin_id": admin.id,
        },
    ]


@pytest.mark.asyncio
async def test_admin_delete_slot_requires_admin() -> None:
    slot = make_slot()
    repository = FakeAdminRepository(slot=slot, has_bookings=False)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.delete_slot(teacher, slot_id=slot.id)

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_delete_slot_returns_not_found_for_missing_slot() -> None:
    slot_id = uuid4()
    repository = FakeAdminRepository(slot=None, has_bookings=False)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(NotFoundException):
        await service.delete_slot(admin, slot_id=slot_id)

    assert repository.calls == [{"method": "get_slot_by_id", "slot_id": slot_id}]


@pytest.mark.asyncio
async def test_admin_delete_slot_returns_conflict_when_slot_has_bookings() -> None:
    slot = make_slot()
    repository = FakeAdminRepository(slot=slot, has_bookings=True)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(ConflictException):
        await service.delete_slot(admin, slot_id=slot.id)

    assert repository.calls == [
        {"method": "get_slot_by_id", "slot_id": slot.id},
        {"method": "slot_has_bookings", "slot_id": slot.id},
    ]
