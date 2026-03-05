from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum, SlotStatusEnum
from app.modules.scheduling.schemas import SlotCreate
from app.modules.scheduling.service import SchedulingService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


@dataclass(slots=True)
class FakeSlot:
    id: UUID
    teacher_id: UUID
    created_by_admin_id: UUID
    start_at: datetime
    end_at: datetime
    status: SlotStatusEnum
    created_at: datetime
    updated_at: datetime


class FakeSchedulingRepository:
    def __init__(self, overlapping_slot: FakeSlot | None = None) -> None:
        self.overlapping_slot = overlapping_slot
        self.created_slots: list[FakeSlot] = []

    async def create_slot(
        self,
        teacher_id: UUID,
        created_by_admin_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> FakeSlot:
        slot = FakeSlot(
            id=uuid4(),
            teacher_id=teacher_id,
            created_by_admin_id=created_by_admin_id,
            start_at=start_at,
            end_at=end_at,
            status=SlotStatusEnum.OPEN,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.created_slots.append(slot)
        return slot

    async def find_overlapping_slot(
        self,
        teacher_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> FakeSlot | None:
        if self.overlapping_slot is None:
            return None
        if self.overlapping_slot.teacher_id != teacher_id:
            return None
        overlaps = (
            self.overlapping_slot.start_at < end_at
            and self.overlapping_slot.end_at > start_at
        )
        return self.overlapping_slot if overlaps else None


class FakeAuditRepository:
    def __init__(self) -> None:
        self.logs: list[dict[str, object]] = []

    async def create_audit_log(
        self,
        actor_id,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict,
    ) -> None:
        self.logs.append(
            {
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload,
            },
        )


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


@pytest.mark.asyncio
async def test_admin_create_slot_succeeds_and_writes_audit() -> None:
    repository = FakeSchedulingRepository()
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    teacher_id = uuid4()
    start_at = datetime.now(UTC) + timedelta(days=2, hours=1)
    end_at = start_at + timedelta(hours=1)

    slot = await service.create_slot(
        SlotCreate(teacher_id=teacher_id, start_at=start_at, end_at=end_at),
        admin,
    )

    assert slot.teacher_id == teacher_id
    assert slot.created_by_admin_id == admin.id
    assert slot.status == SlotStatusEnum.OPEN
    assert len(audit_repository.logs) == 1
    assert audit_repository.logs[0]["action"] == "admin.slot.create"


@pytest.mark.asyncio
async def test_admin_create_slot_rejects_non_admin() -> None:
    repository = FakeSchedulingRepository()
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)
    teacher_id = uuid4()
    start_at = datetime.now(UTC) + timedelta(days=2)
    end_at = start_at + timedelta(hours=1)

    with pytest.raises(UnauthorizedException):
        await service.create_slot(
            SlotCreate(teacher_id=teacher_id, start_at=start_at, end_at=end_at),
            teacher,
        )

    assert repository.created_slots == []
    assert audit_repository.logs == []


@pytest.mark.asyncio
async def test_admin_create_slot_rejects_short_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = FakeSchedulingRepository()
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    teacher_id = uuid4()
    start_at = datetime.now(UTC) + timedelta(days=2)
    end_at = start_at + timedelta(minutes=20)

    from app.modules.scheduling import service as scheduling_service_module

    monkeypatch.setattr(scheduling_service_module.settings, "slot_min_duration_minutes", 30)

    with pytest.raises(BusinessRuleException):
        await service.create_slot(
            SlotCreate(teacher_id=teacher_id, start_at=start_at, end_at=end_at),
            admin,
        )

    assert repository.created_slots == []
    assert audit_repository.logs == []


@pytest.mark.asyncio
async def test_admin_create_slot_rejects_overlap() -> None:
    teacher_id = uuid4()
    base = datetime.now(UTC) + timedelta(days=3, hours=10)
    overlapping_slot = FakeSlot(
        id=uuid4(),
        teacher_id=teacher_id,
        created_by_admin_id=uuid4(),
        start_at=base,
        end_at=base + timedelta(hours=1),
        status=SlotStatusEnum.OPEN,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository = FakeSchedulingRepository(overlapping_slot=overlapping_slot)
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.create_slot(
            SlotCreate(
                teacher_id=teacher_id,
                start_at=overlapping_slot.start_at + timedelta(minutes=15),
                end_at=overlapping_slot.end_at + timedelta(minutes=15),
            ),
            admin,
        )

    assert repository.created_slots == []
    assert audit_repository.logs == []


@pytest.mark.asyncio
async def test_admin_create_slot_rejects_past_start() -> None:
    repository = FakeSchedulingRepository()
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    teacher_id = uuid4()
    start_at = datetime.now(UTC) - timedelta(minutes=5)
    end_at = start_at + timedelta(hours=1)

    with pytest.raises(BusinessRuleException):
        await service.create_slot(
            SlotCreate(teacher_id=teacher_id, start_at=start_at, end_at=end_at),
            admin,
        )

    assert repository.created_slots == []
    assert audit_repository.logs == []
