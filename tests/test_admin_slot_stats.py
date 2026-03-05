from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import BookingStatusEnum, LessonStatusEnum, RoleEnum, SlotStatusEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


class FakeAdminRepository:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    async def list_slot_status_snapshots(
        self,
        *,
        from_utc,
        to_utc,
    ) -> list[dict]:
        self.calls.append({"from_utc": from_utc, "to_utc": to_utc})
        return self.rows


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_row(
    *,
    slot_id,
    slot_status: SlotStatusEnum,
    booking_status: BookingStatusEnum | None,
    lesson_status: LessonStatusEnum | None,
) -> dict:
    return {
        "slot_id": slot_id,
        "slot_status": slot_status,
        "booking_status": booking_status,
        "lesson_status": lesson_status,
    }


@pytest.mark.asyncio
async def test_admin_slot_stats_aggregates_with_priority_per_slot() -> None:
    slot1 = uuid4()
    slot2 = uuid4()
    slot3 = uuid4()
    slot4 = uuid4()
    slot5 = uuid4()
    slot6 = uuid4()
    slot7 = uuid4()
    slot8 = uuid4()
    rows = [
        make_row(
            slot_id=slot1,
            slot_status=SlotStatusEnum.OPEN,
            booking_status=None,
            lesson_status=None,
        ),
        make_row(
            slot_id=slot2,
            slot_status=SlotStatusEnum.HOLD,
            booking_status=BookingStatusEnum.HOLD,
            lesson_status=None,
        ),
        make_row(
            slot_id=slot3,
            slot_status=SlotStatusEnum.BOOKED,
            booking_status=BookingStatusEnum.CONFIRMED,
            lesson_status=LessonStatusEnum.SCHEDULED,
        ),
        make_row(
            slot_id=slot4,
            slot_status=SlotStatusEnum.BOOKED,
            booking_status=BookingStatusEnum.CONFIRMED,
            lesson_status=LessonStatusEnum.COMPLETED,
        ),
        make_row(
            slot_id=slot5,
            slot_status=SlotStatusEnum.OPEN,
            booking_status=BookingStatusEnum.CANCELED,
            lesson_status=None,
        ),
        make_row(
            slot_id=slot6,
            slot_status=SlotStatusEnum.BLOCKED,
            booking_status=None,
            lesson_status=None,
        ),
        make_row(
            slot_id=slot7,
            slot_status=SlotStatusEnum.BOOKED,
            booking_status=BookingStatusEnum.CONFIRMED,
            lesson_status=LessonStatusEnum.CANCELED,
        ),
        make_row(
            slot_id=slot8,
            slot_status=SlotStatusEnum.BOOKED,
            booking_status=BookingStatusEnum.CONFIRMED,
            lesson_status=None,
        ),
        make_row(
            slot_id=slot8,
            slot_status=SlotStatusEnum.BOOKED,
            booking_status=BookingStatusEnum.CONFIRMED,
            lesson_status=LessonStatusEnum.COMPLETED,
        ),
    ]
    repository = FakeAdminRepository(rows=rows)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.get_slot_stats(
        admin,
        from_utc=None,
        to_utc=None,
    )

    assert result.total_slots == 8
    assert result.open_slots == 1
    assert result.held_slots == 1
    assert result.confirmed_slots == 1
    assert result.canceled_slots == 3
    assert result.completed_slots == 2
    assert repository.calls == [{"from_utc": None, "to_utc": None}]


@pytest.mark.asyncio
async def test_admin_slot_stats_normalizes_utc_filters() -> None:
    repository = FakeAdminRepository(rows=[])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    tz_plus_3 = timezone(timedelta(hours=3))

    await service.get_slot_stats(
        admin,
        from_utc=datetime(2026, 3, 10, 12, 0, tzinfo=tz_plus_3),
        to_utc=datetime(2026, 3, 10, 15, 0, tzinfo=tz_plus_3),
    )

    assert repository.calls == [
        {
            "from_utc": datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            "to_utc": datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        },
    ]


@pytest.mark.asyncio
async def test_admin_slot_stats_requires_admin_role() -> None:
    repository = FakeAdminRepository(rows=[])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.get_slot_stats(teacher, from_utc=None, to_utc=None)

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_slot_stats_validates_datetime_range() -> None:
    repository = FakeAdminRepository(rows=[])
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.get_slot_stats(
            admin,
            from_utc=datetime(2026, 3, 10, 12, 1, tzinfo=UTC),
            to_utc=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        )
