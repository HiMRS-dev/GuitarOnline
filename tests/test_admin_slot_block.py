from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum, SlotStatusEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import NotFoundException, UnauthorizedException


@dataclass(slots=True)
class FakeSlot:
    id: UUID
    teacher_id: UUID
    created_by_admin_id: UUID
    start_at: datetime
    end_at: datetime
    status: SlotStatusEnum
    block_reason: str | None
    blocked_at: datetime | None
    blocked_by_admin_id: UUID | None
    updated_at: datetime


class FakeAdminRepository:
    def __init__(self, slot: FakeSlot | None) -> None:
        self.slot = slot
        self.calls: list[dict[str, object]] = []

    async def get_slot_by_id(self, slot_id: UUID) -> FakeSlot | None:
        self.calls.append({"method": "get_slot_by_id", "slot_id": slot_id})
        if self.slot is None or self.slot.id != slot_id:
            return None
        return self.slot

    async def block_slot(
        self,
        *,
        slot: FakeSlot,
        reason: str,
        admin_id: UUID,
        blocked_at: datetime,
    ) -> FakeSlot:
        self.calls.append(
            {
                "method": "block_slot",
                "slot_id": slot.id,
                "reason": reason,
                "admin_id": admin_id,
            },
        )
        slot.status = SlotStatusEnum.BLOCKED
        slot.block_reason = reason
        slot.blocked_at = blocked_at
        slot.blocked_by_admin_id = admin_id
        slot.updated_at = blocked_at
        return slot


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_slot() -> FakeSlot:
    return FakeSlot(
        id=uuid4(),
        teacher_id=uuid4(),
        created_by_admin_id=uuid4(),
        start_at=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
        end_at=datetime(2026, 3, 12, 11, 0, tzinfo=UTC),
        status=SlotStatusEnum.OPEN,
        block_reason=None,
        blocked_at=None,
        blocked_by_admin_id=None,
        updated_at=datetime(2026, 3, 5, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_admin_block_slot_succeeds() -> None:
    slot = make_slot()
    repository = FakeAdminRepository(slot=slot)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.block_slot(
        admin,
        slot_id=slot.id,
        reason="Teacher unavailable",
    )

    assert result.slot_id == slot.id
    assert result.slot_status == SlotStatusEnum.BLOCKED
    assert result.block_reason == "Teacher unavailable"
    assert result.blocked_by_admin_id == admin.id
    assert repository.calls[0] == {"method": "get_slot_by_id", "slot_id": slot.id}
    assert repository.calls[1]["method"] == "block_slot"


@pytest.mark.asyncio
async def test_admin_block_slot_requires_admin() -> None:
    slot = make_slot()
    repository = FakeAdminRepository(slot=slot)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.block_slot(student, slot_id=slot.id, reason="Reason")

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_block_slot_returns_not_found_when_slot_missing() -> None:
    slot_id = uuid4()
    repository = FakeAdminRepository(slot=None)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(NotFoundException):
        await service.block_slot(admin, slot_id=slot_id, reason="Reason")

    assert repository.calls == [{"method": "get_slot_by_id", "slot_id": slot_id}]
