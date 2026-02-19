from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import app.modules.booking.service as booking_service_module
from app.core.enums import BookingStatusEnum, PackageStatusEnum, RoleEnum, SlotStatusEnum
from app.modules.booking.schemas import (
    BookingCancelRequest,
    BookingHoldRequest,
    BookingRescheduleRequest,
)
from app.modules.booking.service import BookingService, settings


@dataclass
class FakeSlot:
    id: UUID
    teacher_id: UUID
    start_at: datetime
    status: SlotStatusEnum


@dataclass
class FakePackage:
    id: UUID
    student_id: UUID
    status: PackageStatusEnum
    expires_at: datetime
    lessons_total: int
    lessons_left: int


@dataclass
class FakeBooking:
    id: UUID
    slot_id: UUID
    slot: FakeSlot
    student_id: UUID
    teacher_id: UUID
    package_id: UUID | None
    status: BookingStatusEnum
    hold_expires_at: datetime | None = None
    confirmed_at: datetime | None = None
    canceled_at: datetime | None = None
    cancellation_reason: str | None = None
    refund_returned: bool = False
    rescheduled_from_booking_id: UUID | None = None


class FakeBookingRepository:
    def __init__(
        self,
        slots: dict[UUID, FakeSlot],
        bookings: dict[UUID, FakeBooking] | None = None,
    ) -> None:
        self._slots = slots
        self._bookings: dict[UUID, FakeBooking] = bookings or {}

    async def create_booking_hold(
        self,
        slot_id: UUID,
        student_id: UUID,
        teacher_id: UUID,
        package_id: UUID,
        hold_expires_at: datetime,
    ) -> FakeBooking:
        booking = FakeBooking(
            id=uuid4(),
            slot_id=slot_id,
            slot=self._slots[slot_id],
            student_id=student_id,
            teacher_id=teacher_id,
            package_id=package_id,
            status=BookingStatusEnum.HOLD,
            hold_expires_at=hold_expires_at,
        )
        self._bookings[booking.id] = booking
        return booking

    async def get_booking_by_id(self, booking_id: UUID) -> FakeBooking | None:
        return self._bookings.get(booking_id)

    async def save(self, booking: FakeBooking) -> FakeBooking:
        self._bookings[booking.id] = booking
        return booking

    async def find_expired_holds(self, now: datetime) -> list[FakeBooking]:
        return [
            booking
            for booking in self._bookings.values()
            if booking.status == BookingStatusEnum.HOLD
            and booking.hold_expires_at is not None
            and booking.hold_expires_at <= now
        ]


class FakeSchedulingRepository:
    def __init__(self, slots: dict[UUID, FakeSlot]) -> None:
        self._slots = slots

    async def get_slot_by_id(self, slot_id: UUID) -> FakeSlot | None:
        return self._slots.get(slot_id)

    async def set_slot_status(self, slot: FakeSlot, status: SlotStatusEnum) -> FakeSlot:
        slot.status = status
        return slot


class FakeBillingRepository:
    def __init__(self, packages: dict[UUID, FakePackage]) -> None:
        self._packages = packages
        self.return_calls = 0
        self.consume_calls = 0

    async def get_package_by_id(self, package_id: UUID) -> FakePackage | None:
        return self._packages.get(package_id)

    async def consume_package_lesson(self, package: FakePackage) -> None:
        package.lessons_left -= 1
        self.consume_calls += 1

    async def return_package_lesson(self, package: FakePackage) -> None:
        package.lessons_left += 1
        self.return_calls += 1


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def create_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        self.events.append(
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": payload,
            },
        )


def make_actor(user_id: UUID, role: RoleEnum = RoleEnum.STUDENT) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, role=SimpleNamespace(name=role))


def make_service(
    *,
    slots: dict[UUID, FakeSlot],
    packages: dict[UUID, FakePackage],
    bookings: dict[UUID, FakeBooking] | None = None,
) -> tuple[
    BookingService,
    FakeBookingRepository,
    FakeBillingRepository,
    FakeSchedulingRepository,
    FakeAuditRepository,
]:
    booking_repo = FakeBookingRepository(slots=slots, bookings=bookings)
    scheduling_repo = FakeSchedulingRepository(slots=slots)
    billing_repo = FakeBillingRepository(packages=packages)
    audit_repo = FakeAuditRepository()
    service = BookingService(
        booking_repository=booking_repo,
        scheduling_repository=scheduling_repo,
        billing_repository=billing_repo,
        audit_repository=audit_repo,
    )
    return service, booking_repo, billing_repo, scheduling_repo, audit_repo


@pytest.mark.asyncio
async def test_hold_sets_10_minute_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=48),
        status=SlotStatusEnum.OPEN,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=10,
        lessons_left=10,
    )

    service, _, _, _, _ = make_service(slots={slot_id: slot}, packages={package_id: package})
    actor = make_actor(student_id, RoleEnum.STUDENT)

    booking = await service.hold_booking(
        BookingHoldRequest(slot_id=slot_id, package_id=package_id),
        actor,
    )

    assert booking.status == BookingStatusEnum.HOLD
    assert booking.hold_expires_at == fixed_now + timedelta(minutes=settings.booking_hold_minutes)
    assert slot.status == SlotStatusEnum.HOLD


@pytest.mark.asyncio
async def test_cancel_more_than_24h_returns_lesson(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()
    booking_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=25),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=8,
        lessons_left=3,
    )
    booking = FakeBooking(
        id=booking_id,
        slot_id=slot_id,
        slot=slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=package_id,
        status=BookingStatusEnum.CONFIRMED,
    )

    service, _, billing_repo, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    canceled = await service.cancel_booking(booking_id, BookingCancelRequest(reason="test"), actor)

    assert canceled.status == BookingStatusEnum.CANCELED
    assert canceled.refund_returned is True
    assert billing_repo.return_calls == 1
    assert package.lessons_left == 4
    assert slot.status == SlotStatusEnum.OPEN


@pytest.mark.asyncio
async def test_cancel_less_than_24h_burns_lesson(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()
    booking_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=23),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=8,
        lessons_left=3,
    )
    booking = FakeBooking(
        id=booking_id,
        slot_id=slot_id,
        slot=slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=package_id,
        status=BookingStatusEnum.CONFIRMED,
    )

    service, _, billing_repo, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    canceled = await service.cancel_booking(booking_id, BookingCancelRequest(reason="test"), actor)

    assert canceled.status == BookingStatusEnum.CANCELED
    assert canceled.refund_returned is False
    assert billing_repo.return_calls == 0
    assert package.lessons_left == 3
    assert slot.status == SlotStatusEnum.OPEN


@pytest.mark.asyncio
async def test_reschedule_is_cancel_plus_new_booking(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    old_slot_id = uuid4()
    new_slot_id = uuid4()
    package_id = uuid4()
    old_booking_id = uuid4()

    old_slot = FakeSlot(
        id=old_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=30),
        status=SlotStatusEnum.BOOKED,
    )
    new_slot = FakeSlot(
        id=new_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=48),
        status=SlotStatusEnum.OPEN,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=10,
        lessons_left=4,
    )
    old_booking = FakeBooking(
        id=old_booking_id,
        slot_id=old_slot_id,
        slot=old_slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=package_id,
        status=BookingStatusEnum.CONFIRMED,
    )

    service, booking_repo, billing_repo, _, audit_repo = make_service(
        slots={old_slot_id: old_slot, new_slot_id: new_slot},
        packages={package_id: package},
        bookings={old_booking_id: old_booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    new_booking = await service.reschedule_booking(
        old_booking_id,
        BookingRescheduleRequest(new_slot_id=new_slot_id),
        actor,
    )

    assert booking_repo._bookings[old_booking_id].status == BookingStatusEnum.CANCELED
    assert new_booking.status == BookingStatusEnum.CONFIRMED
    assert new_booking.rescheduled_from_booking_id == old_booking_id
    assert old_slot.status == SlotStatusEnum.OPEN
    assert new_slot.status == SlotStatusEnum.BOOKED
    assert billing_repo.return_calls == 1
    assert billing_repo.consume_calls == 1
    assert package.lessons_left == 4
    assert any(event["event_type"] == "booking.rescheduled" for event in audit_repo.events)
