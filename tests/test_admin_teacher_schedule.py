from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum
from app.modules.scheduling.service import SchedulingService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


@dataclass(slots=True)
class FakeScheduleWindow:
    id: UUID
    teacher_id: UUID
    weekday: int
    start_local_time: time
    end_local_time: time
    created_at: datetime
    updated_at: datetime


class FakeSchedulingRepository:
    def __init__(self, *, teacher_timezone: str | None = "UTC") -> None:
        self.teacher_timezone = teacher_timezone
        self.windows: list[FakeScheduleWindow] = []
        self.locked_teacher_ids: list[UUID] = []

    async def get_teacher_timezone(self, teacher_id: UUID) -> str | None:
        _ = teacher_id
        return self.teacher_timezone

    async def lock_teacher_for_slot_mutation(self, teacher_id: UUID) -> None:
        self.locked_teacher_ids.append(teacher_id)

    async def list_teacher_weekly_schedule_windows(
        self,
        teacher_id: UUID,
    ) -> list[FakeScheduleWindow]:
        return [item for item in self.windows if item.teacher_id == teacher_id]

    async def replace_teacher_weekly_schedule_windows(
        self,
        *,
        teacher_id: UUID,
        windows: list[tuple[int, time, time]],
    ) -> list[FakeScheduleWindow]:
        self.windows = [item for item in self.windows if item.teacher_id != teacher_id]
        created: list[FakeScheduleWindow] = []
        for weekday, start_local_time, end_local_time in windows:
            created.append(
                FakeScheduleWindow(
                    id=uuid4(),
                    teacher_id=teacher_id,
                    weekday=weekday,
                    start_local_time=start_local_time,
                    end_local_time=end_local_time,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
            )
        self.windows.extend(created)
        return created


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
async def test_admin_replace_teacher_schedule_returns_dual_time_and_writes_audit() -> None:
    repository = FakeSchedulingRepository(teacher_timezone="UTC")
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    teacher_id = uuid4()

    result = await service.replace_teacher_weekly_schedule(
        teacher_id=teacher_id,
        windows=[
            (0, time(10, 0), time(12, 0)),
            (2, time(14, 30), time(16, 0)),
        ],
        actor=admin,
    )

    assert result["teacher_id"] == teacher_id
    assert result["timezone"] == "UTC"
    assert len(result["windows"]) == 2
    first_window = result["windows"][0]
    assert first_window["weekday"] == 0
    assert first_window["start_local_time"] == time(10, 0)
    assert first_window["end_local_time"] == time(12, 0)
    assert first_window["moscow_start_time"] == time(13, 0)
    assert first_window["moscow_end_time"] == time(15, 0)
    assert repository.locked_teacher_ids == [teacher_id]
    assert len(audit_repository.logs) == 1
    assert audit_repository.logs[0]["action"] == "admin.teacher.schedule.replace"


@pytest.mark.asyncio
async def test_admin_replace_teacher_schedule_rejects_overlaps() -> None:
    repository = FakeSchedulingRepository(teacher_timezone="Europe/Moscow")
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.replace_teacher_weekly_schedule(
            teacher_id=uuid4(),
            windows=[
                (1, time(10, 0), time(12, 0)),
                (1, time(11, 30), time(13, 0)),
            ],
            actor=admin,
        )

    assert audit_repository.logs == []


@pytest.mark.asyncio
async def test_admin_replace_teacher_schedule_rejects_invalid_timezone() -> None:
    repository = FakeSchedulingRepository(teacher_timezone="Europe/Invalid")
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.replace_teacher_weekly_schedule(
            teacher_id=uuid4(),
            windows=[(4, time(9, 0), time(11, 0))],
            actor=admin,
        )

    assert audit_repository.logs == []


@pytest.mark.asyncio
async def test_admin_get_teacher_schedule_requires_admin_role() -> None:
    repository = FakeSchedulingRepository(teacher_timezone="UTC")
    audit_repository = FakeAuditRepository()
    service = SchedulingService(repository=repository, audit_repository=audit_repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.get_teacher_weekly_schedule(
            teacher_id=uuid4(),
            actor=teacher,
        )
