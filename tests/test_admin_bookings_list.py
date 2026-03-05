from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import BookingStatusEnum, RoleEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


class FakeAdminRepository:
    def __init__(self, items: list[dict], total: int) -> None:
        self.items = items
        self.total = total
        self.calls: list[dict[str, object]] = []

    async def list_bookings(
        self,
        *,
        teacher_id,
        student_id,
        status,
        from_utc,
        to_utc,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        self.calls.append(
            {
                "teacher_id": teacher_id,
                "student_id": student_id,
                "status": status,
                "from_utc": from_utc,
                "to_utc": to_utc,
                "limit": limit,
                "offset": offset,
            },
        )
        return self.items, self.total


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_item() -> dict:
    return {
        "booking_id": uuid4(),
        "slot_id": uuid4(),
        "student_id": uuid4(),
        "teacher_id": uuid4(),
        "package_id": uuid4(),
        "status": BookingStatusEnum.CONFIRMED,
        "slot_start_at_utc": datetime(2026, 3, 11, 10, 0, tzinfo=UTC),
        "slot_end_at_utc": datetime(2026, 3, 11, 11, 0, tzinfo=UTC),
        "hold_expires_at_utc": None,
        "confirmed_at_utc": datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
        "canceled_at_utc": None,
        "cancellation_reason": None,
        "refund_returned": False,
        "rescheduled_from_booking_id": None,
        "created_at_utc": datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
        "updated_at_utc": datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_admin_bookings_list_passes_filters_and_serializes_rows() -> None:
    item = make_item()
    repository = FakeAdminRepository(items=[item], total=1)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    teacher_id = uuid4()
    student_id = uuid4()

    items, total = await service.list_bookings(
        admin,
        teacher_id=teacher_id,
        student_id=student_id,
        status=BookingStatusEnum.HOLD,
        from_utc=datetime(2026, 3, 11, 10, 0, tzinfo=UTC),
        to_utc=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
        limit=20,
        offset=5,
    )

    assert total == 1
    assert items[0].booking_id == item["booking_id"]
    assert items[0].status == BookingStatusEnum.CONFIRMED
    assert repository.calls == [
        {
            "teacher_id": teacher_id,
            "student_id": student_id,
            "status": BookingStatusEnum.HOLD,
            "from_utc": datetime(2026, 3, 11, 10, 0, tzinfo=UTC),
            "to_utc": datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
            "limit": 20,
            "offset": 5,
        },
    ]


@pytest.mark.asyncio
async def test_admin_bookings_list_normalizes_datetime_filters_to_utc() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    tz_plus_3 = timezone(timedelta(hours=3))
    from_local = datetime(2026, 3, 11, 12, 0, tzinfo=tz_plus_3)
    to_local = datetime(2026, 3, 12, 12, 0, tzinfo=tz_plus_3)

    await service.list_bookings(
        admin,
        teacher_id=None,
        student_id=None,
        status=None,
        from_utc=from_local,
        to_utc=to_local,
        limit=10,
        offset=0,
    )

    assert repository.calls == [
        {
            "teacher_id": None,
            "student_id": None,
            "status": None,
            "from_utc": datetime(2026, 3, 11, 9, 0, tzinfo=UTC),
            "to_utc": datetime(2026, 3, 12, 9, 0, tzinfo=UTC),
            "limit": 10,
            "offset": 0,
        },
    ]


@pytest.mark.asyncio
async def test_admin_bookings_list_requires_admin_role() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.list_bookings(
            teacher,
            teacher_id=None,
            student_id=None,
            status=None,
            from_utc=None,
            to_utc=None,
            limit=20,
            offset=0,
        )

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_bookings_list_validates_datetime_range() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.list_bookings(
            admin,
            teacher_id=None,
            student_id=None,
            status=None,
            from_utc=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
            to_utc=datetime(2026, 3, 12, 9, 59, tzinfo=UTC),
            limit=20,
            offset=0,
        )
