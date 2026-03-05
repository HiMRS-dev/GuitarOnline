from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import (
    BookingStatusEnum,
    RoleEnum,
    SlotBookingAggregateStatusEnum,
    SlotStatusEnum,
)
from app.modules.admin.service import AdminService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


class FakeAdminRepository:
    def __init__(self, items: list[dict], total: int) -> None:
        self.items = items
        self.total = total
        self.calls: list[dict[str, object]] = []

    async def list_slots(
        self,
        *,
        teacher_id,
        from_utc,
        to_utc,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        self.calls.append(
            {
                "teacher_id": teacher_id,
                "from_utc": from_utc,
                "to_utc": to_utc,
                "limit": limit,
                "offset": offset,
            },
        )
        return self.items, self.total


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_item(*, slot_status: SlotStatusEnum, booking_status: BookingStatusEnum | None) -> dict:
    return {
        "slot_id": uuid4(),
        "teacher_id": uuid4(),
        "created_by_admin_id": uuid4(),
        "start_at_utc": datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
        "end_at_utc": datetime(2026, 3, 7, 13, 0, tzinfo=UTC),
        "slot_status": slot_status,
        "booking_id": uuid4() if booking_status is not None else None,
        "booking_status": booking_status,
        "created_at_utc": datetime(2026, 3, 5, 10, 0, tzinfo=UTC),
        "updated_at_utc": datetime(2026, 3, 5, 10, 15, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_admin_slots_list_maps_aggregated_booking_status() -> None:
    repository = FakeAdminRepository(
        items=[
            make_item(slot_status=SlotStatusEnum.OPEN, booking_status=None),
            make_item(slot_status=SlotStatusEnum.HOLD, booking_status=BookingStatusEnum.HOLD),
            make_item(
                slot_status=SlotStatusEnum.BOOKED,
                booking_status=BookingStatusEnum.CONFIRMED,
            ),
            make_item(
                slot_status=SlotStatusEnum.OPEN,
                booking_status=BookingStatusEnum.CANCELED,
            ),
        ],
        total=4,
    )
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    items, total = await service.list_slots(
        admin,
        teacher_id=None,
        from_utc=None,
        to_utc=None,
        limit=20,
        offset=0,
    )

    assert total == 4
    assert [item.aggregated_booking_status for item in items] == [
        SlotBookingAggregateStatusEnum.OPEN,
        SlotBookingAggregateStatusEnum.HELD,
        SlotBookingAggregateStatusEnum.CONFIRMED,
        SlotBookingAggregateStatusEnum.OPEN,
    ]


@pytest.mark.asyncio
async def test_admin_slots_list_normalizes_datetime_filters_to_utc() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    teacher_id = uuid4()

    tz_plus_3 = timezone(timedelta(hours=3))
    from_local = datetime(2026, 3, 9, 12, 0, tzinfo=tz_plus_3)
    to_local = datetime(2026, 3, 10, 12, 0, tzinfo=tz_plus_3)

    await service.list_slots(
        admin,
        teacher_id=teacher_id,
        from_utc=from_local,
        to_utc=to_local,
        limit=10,
        offset=5,
    )

    assert repository.calls == [
        {
            "teacher_id": teacher_id,
            "from_utc": datetime(2026, 3, 9, 9, 0, tzinfo=UTC),
            "to_utc": datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            "limit": 10,
            "offset": 5,
        },
    ]


@pytest.mark.asyncio
async def test_admin_slots_list_requires_admin_role() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.list_slots(
            teacher,
            teacher_id=None,
            from_utc=None,
            to_utc=None,
            limit=20,
            offset=0,
        )

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_slots_list_validates_datetime_range() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.list_slots(
            admin,
            teacher_id=None,
            from_utc=datetime(2026, 3, 11, 10, 0, tzinfo=UTC),
            to_utc=datetime(2026, 3, 11, 9, 59, tzinfo=UTC),
            limit=20,
            offset=0,
        )
