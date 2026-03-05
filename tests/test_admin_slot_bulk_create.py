from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum, SlotStatusEnum
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
    def __init__(self, existing_slots: list[FakeSlot] | None = None) -> None:
        self.existing_slots = existing_slots or []
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
        self.existing_slots.append(slot)
        self.created_slots.append(slot)
        return slot

    async def find_overlapping_slot(
        self,
        teacher_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> FakeSlot | None:
        for slot in self.existing_slots:
            if slot.teacher_id != teacher_id:
                continue
            if slot.start_at < end_at and slot.end_at > start_at:
                return slot
        return None


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
async def test_admin_bulk_create_slots_creates_and_skips_with_summary_audit() -> None:
    teacher_id = uuid4()
    target_day = date.today() + timedelta(days=7)
    existing_overlap = FakeSlot(
        id=uuid4(),
        teacher_id=teacher_id,
        created_by_admin_id=uuid4(),
        start_at=datetime.combine(target_day, time(10, 0), tzinfo=UTC),
        end_at=datetime.combine(target_day, time(11, 0), tzinfo=UTC),
        status=SlotStatusEnum.OPEN,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository = FakeSchedulingRepository(existing_slots=[existing_overlap])
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    created, skipped = await service.bulk_create_slots(
        teacher_id=teacher_id,
        date_from_utc=target_day,
        date_to_utc=target_day,
        weekdays=[target_day.weekday()],
        start_time_utc=time(10, 0),
        end_time_utc=time(12, 0),
        slot_duration_minutes=60,
        actor=admin,
    )

    assert len(created) == 1
    assert len(skipped) == 1
    assert "overlaps with an existing slot" in skipped[0]["reason"]
    assert len(audit_repository.logs) == 2
    assert audit_repository.logs[-1]["action"] == "admin.slot.bulk_create"
    assert audit_repository.logs[-1]["payload"]["created_count"] == 1
    assert audit_repository.logs[-1]["payload"]["skipped_count"] == 1


@pytest.mark.asyncio
async def test_admin_bulk_create_slots_requires_admin() -> None:
    repository = FakeSchedulingRepository()
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    student = make_actor(RoleEnum.STUDENT)
    target_day = date.today() + timedelta(days=7)

    with pytest.raises(UnauthorizedException):
        await service.bulk_create_slots(
            teacher_id=uuid4(),
            date_from_utc=target_day,
            date_to_utc=target_day,
            weekdays=[target_day.weekday()],
            start_time_utc=time(10, 0),
            end_time_utc=time(12, 0),
            slot_duration_minutes=60,
            actor=student,
        )

    assert repository.created_slots == []
    assert audit_repository.logs == []


@pytest.mark.asyncio
async def test_admin_bulk_create_slots_validates_date_range() -> None:
    repository = FakeSchedulingRepository()
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.bulk_create_slots(
            teacher_id=uuid4(),
            date_from_utc=date.today() + timedelta(days=8),
            date_to_utc=date.today() + timedelta(days=7),
            weekdays=[0],
            start_time_utc=time(10, 0),
            end_time_utc=time(12, 0),
            slot_duration_minutes=60,
            actor=admin,
        )


@pytest.mark.asyncio
async def test_admin_bulk_create_slots_enforces_candidate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeSchedulingRepository()
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    target_day = date.today() + timedelta(days=7)

    from app.modules.scheduling import service as scheduling_service_module

    monkeypatch.setattr(scheduling_service_module.settings, "slot_bulk_create_max_slots", 1)

    with pytest.raises(BusinessRuleException):
        await service.bulk_create_slots(
            teacher_id=uuid4(),
            date_from_utc=target_day,
            date_to_utc=target_day,
            weekdays=[target_day.weekday()],
            start_time_utc=time(10, 0),
            end_time_utc=time(12, 0),
            slot_duration_minutes=60,
            actor=admin,
        )
