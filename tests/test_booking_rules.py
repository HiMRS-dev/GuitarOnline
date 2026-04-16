from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import app.modules.booking.service as booking_service_module
from app.core.enums import (
    BookingStatusEnum,
    LessonStatusEnum,
    PackageStatusEnum,
    RoleEnum,
    SlotStatusEnum,
)
from app.modules.booking.schemas import (
    BookingCancelRequest,
    BookingHoldRequest,
    BookingRescheduleRequest,
)
from app.modules.booking.service import BookingService, settings
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


@dataclass
class FakeSlot:
    id: UUID
    teacher_id: UUID
    start_at: datetime
    end_at: datetime
    status: SlotStatusEnum


@dataclass
class FakePackage:
    id: UUID
    student_id: UUID
    status: PackageStatusEnum
    expires_at: datetime
    lessons_total: int
    lessons_left: int
    lessons_reserved: int = 0


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


@dataclass
class FakeLesson:
    id: UUID
    booking_id: UUID
    student_id: UUID
    teacher_id: UUID
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    status: LessonStatusEnum = LessonStatusEnum.SCHEDULED
    topic: str | None = None
    notes: str | None = None


class FakeBookingRepository:
    def __init__(
        self,
        slots: dict[UUID, FakeSlot],
        bookings: dict[UUID, FakeBooking] | None = None,
        teacher_students_with_packages: tuple[list[dict], int] | None = None,
    ) -> None:
        self._slots = slots
        self._bookings: dict[UUID, FakeBooking] = bookings or {}
        if teacher_students_with_packages is None:
            self._teacher_students_with_packages = ([], 0)
        else:
            self._teacher_students_with_packages = teacher_students_with_packages

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

    async def get_booking_by_id_for_update(self, booking_id: UUID) -> FakeBooking | None:
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

    async def get_active_booking_for_slot(self, slot_id: UUID) -> FakeBooking | None:
        for booking in self._bookings.values():
            if booking.slot_id != slot_id:
                continue
            if booking.status in (BookingStatusEnum.HOLD, BookingStatusEnum.CONFIRMED):
                return booking
        return None

    async def get_reschedule_successor(self, booking_id: UUID) -> FakeBooking | None:
        for booking in self._bookings.values():
            if booking.rescheduled_from_booking_id == booking_id:
                return booking
        return None

    async def list_teacher_students_with_packages(
        self,
        teacher_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        _ = teacher_id, limit, offset
        return self._teacher_students_with_packages


class FakeSchedulingRepository:
    def __init__(self, slots: dict[UUID, FakeSlot]) -> None:
        self._slots = slots
        self.locked_teacher_ids: list[UUID] = []

    async def get_slot_by_id(self, slot_id: UUID) -> FakeSlot | None:
        return self._slots.get(slot_id)

    async def get_slot_by_id_for_update(self, slot_id: UUID) -> FakeSlot | None:
        return self._slots.get(slot_id)

    async def lock_teacher_for_slot_mutation(self, teacher_id: UUID) -> None:
        self.locked_teacher_ids.append(teacher_id)

    async def set_slot_status(self, slot: FakeSlot, status: SlotStatusEnum) -> FakeSlot:
        slot.status = status
        return slot

    async def split_open_slot_for_booking(
        self,
        *,
        slot: FakeSlot,
        booking_start_at: datetime,
        booking_end_at: datetime,
    ) -> FakeSlot:
        original_start = slot.start_at
        original_end = slot.end_at

        if booking_start_at > original_start:
            left_slot_id = uuid4()
            self._slots[left_slot_id] = FakeSlot(
                id=left_slot_id,
                teacher_id=slot.teacher_id,
                start_at=original_start,
                end_at=booking_start_at,
                status=SlotStatusEnum.OPEN,
            )

        if booking_end_at < original_end:
            right_slot_id = uuid4()
            self._slots[right_slot_id] = FakeSlot(
                id=right_slot_id,
                teacher_id=slot.teacher_id,
                start_at=booking_end_at,
                end_at=original_end,
                status=SlotStatusEnum.OPEN,
            )

        slot.start_at = booking_start_at
        slot.end_at = booking_end_at
        return slot


class FakeBillingRepository:
    def __init__(self, packages: dict[UUID, FakePackage]) -> None:
        self._packages = packages
        self.release_calls = 0
        self.reserve_calls = 0
        self.consume_reserved_calls = 0

    async def get_package_by_id(self, package_id: UUID) -> FakePackage | None:
        return self._packages.get(package_id)

    async def get_package_by_id_for_update(self, package_id: UUID) -> FakePackage | None:
        return self._packages.get(package_id)

    async def reserve_package_lesson(self, package: FakePackage) -> None:
        package.lessons_reserved += 1
        self.reserve_calls += 1

    async def release_package_reservation(self, package: FakePackage) -> None:
        if package.lessons_reserved <= 0:
            return
        package.lessons_reserved -= 1
        self.release_calls += 1

    async def consume_reserved_package_lesson(self, package: FakePackage) -> None:
        if package.lessons_reserved <= 0:
            return
        package.lessons_reserved -= 1
        package.lessons_left -= 1
        self.consume_reserved_calls += 1


class FakeLessonsRepository:
    def __init__(self, lessons: dict[UUID, FakeLesson] | None = None) -> None:
        self._lessons_by_booking: dict[UUID, FakeLesson] = lessons or {}
        self.create_calls = 0

    async def get_lesson_by_booking_id(self, booking_id: UUID) -> FakeLesson | None:
        return self._lessons_by_booking.get(booking_id)

    async def create_lesson(
        self,
        booking_id: UUID,
        student_id: UUID,
        teacher_id: UUID,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        topic: str | None,
        notes: str | None,
    ) -> FakeLesson:
        lesson = FakeLesson(
            id=uuid4(),
            booking_id=booking_id,
            student_id=student_id,
            teacher_id=teacher_id,
            scheduled_start_at=scheduled_start_at,
            scheduled_end_at=scheduled_end_at,
            topic=topic,
            notes=notes,
        )
        self._lessons_by_booking[booking_id] = lesson
        self.create_calls += 1
        return lesson

    async def update_lesson(self, lesson: FakeLesson, **changes) -> FakeLesson:
        for key, value in changes.items():
            if value is not None:
                setattr(lesson, key, value)
        return lesson


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.audit_logs: list[dict] = []

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

    async def create_audit_log(
        self,
        actor_id,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict,
    ) -> None:
        self.audit_logs.append(
            {
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
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
    lessons: dict[UUID, FakeLesson] | None = None,
    teacher_students_with_packages: tuple[list[dict], int] | None = None,
) -> tuple[
    BookingService,
    FakeBookingRepository,
    FakeBillingRepository,
    FakeSchedulingRepository,
    FakeLessonsRepository,
    FakeAuditRepository,
]:
    booking_repo = FakeBookingRepository(
        slots=slots,
        bookings=bookings,
        teacher_students_with_packages=teacher_students_with_packages,
    )
    scheduling_repo = FakeSchedulingRepository(slots=slots)
    billing_repo = FakeBillingRepository(packages=packages)
    lessons_repo = FakeLessonsRepository(lessons=lessons)
    audit_repo = FakeAuditRepository()
    service = BookingService(
        booking_repository=booking_repo,
        scheduling_repository=scheduling_repo,
        billing_repository=billing_repo,
        lessons_repository=lessons_repo,
        audit_repository=audit_repo,
    )
    return service, booking_repo, billing_repo, scheduling_repo, lessons_repo, audit_repo


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
        end_at=fixed_now + timedelta(hours=49),
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

    service, _, _, _, _, _ = make_service(slots={slot_id: slot}, packages={package_id: package})
    actor = make_actor(student_id, RoleEnum.STUDENT)

    booking = await service.hold_booking(
        BookingHoldRequest(slot_id=slot_id, package_id=package_id),
        actor,
    )

    assert booking.status == BookingStatusEnum.HOLD
    assert booking.hold_expires_at == fixed_now + timedelta(minutes=settings.booking_hold_minutes)
    assert slot.status == SlotStatusEnum.HOLD


@pytest.mark.asyncio
async def test_hold_allows_custom_interval_and_splits_source_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=22),
        end_at=fixed_now + timedelta(hours=28),
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
    custom_start = fixed_now + timedelta(hours=23)
    custom_end = fixed_now + timedelta(hours=24)

    service, booking_repo, _, scheduling_repo, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    booking = await service.hold_booking(
        BookingHoldRequest(
            slot_id=slot_id,
            package_id=package_id,
            start_at=custom_start,
            end_at=custom_end,
        ),
        actor,
    )

    assert booking.status == BookingStatusEnum.HOLD
    assert booking.slot_id == slot_id
    assert booking.slot.start_at == custom_start
    assert booking.slot.end_at == custom_end
    assert booking_repo._bookings[booking.id].slot.start_at == custom_start
    assert booking_repo._bookings[booking.id].slot.end_at == custom_end
    assert scheduling_repo.locked_teacher_ids == [teacher_id]
    split_remainders = [
        item
        for item in scheduling_repo._slots.values()
        if item.id != slot_id and item.teacher_id == teacher_id
    ]
    assert len(split_remainders) == 2
    assert sorted(item.start_at for item in split_remainders) == [
        fixed_now + timedelta(hours=22),
        fixed_now + timedelta(hours=24),
    ]
    assert sorted(item.end_at for item in split_remainders) == [
        fixed_now + timedelta(hours=23),
        fixed_now + timedelta(hours=28),
    ]


@pytest.mark.asyncio
async def test_hold_rejects_custom_interval_outside_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=24),
        end_at=fixed_now + timedelta(hours=30),
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

    service, _, _, _, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    with pytest.raises(BusinessRuleException, match="inside selected slot"):
        await service.hold_booking(
            BookingHoldRequest(
                slot_id=slot_id,
                package_id=package_id,
                start_at=fixed_now + timedelta(hours=23),
                end_at=fixed_now + timedelta(hours=24),
            ),
            actor,
        )


@pytest.mark.asyncio
async def test_hold_rejects_when_slot_has_active_booking_even_if_slot_status_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    other_student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()
    existing_booking_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=24),
        end_at=fixed_now + timedelta(hours=25),
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
    existing_booking = FakeBooking(
        id=existing_booking_id,
        slot_id=slot_id,
        slot=slot,
        student_id=other_student_id,
        teacher_id=teacher_id,
        package_id=uuid4(),
        status=BookingStatusEnum.CONFIRMED,
    )

    service, booking_repo, _, _, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={existing_booking_id: existing_booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    with pytest.raises(BusinessRuleException, match="Slot is not available"):
        await service.hold_booking(
            BookingHoldRequest(slot_id=slot_id, package_id=package_id),
            actor,
        )

    assert len(booking_repo._bookings) == 1
    assert slot.status == SlotStatusEnum.OPEN


@pytest.mark.asyncio
async def test_hold_allows_rebooking_when_only_terminal_booking_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()
    old_booking_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=24),
        end_at=fixed_now + timedelta(hours=25),
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
    old_booking = FakeBooking(
        id=old_booking_id,
        slot_id=slot_id,
        slot=slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=package_id,
        status=BookingStatusEnum.CANCELED,
    )

    service, booking_repo, _, _, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={old_booking_id: old_booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    new_hold = await service.hold_booking(
        BookingHoldRequest(slot_id=slot_id, package_id=package_id),
        actor,
    )

    assert new_hold.status == BookingStatusEnum.HOLD
    assert new_hold.slot_id == slot_id
    assert len(booking_repo._bookings) == 2
    assert slot.status == SlotStatusEnum.HOLD


@pytest.mark.asyncio
async def test_confirm_creates_lesson_and_emits_lesson_created_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=36),
        end_at=fixed_now + timedelta(hours=37),
        status=SlotStatusEnum.OPEN,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=10),
        lessons_total=8,
        lessons_left=8,
    )

    service, _, billing_repo, _, lessons_repo, audit_repo = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    hold = await service.hold_booking(
        BookingHoldRequest(slot_id=slot_id, package_id=package_id),
        actor,
    )
    confirmed = await service.confirm_booking(hold.id, actor)
    lesson = await lessons_repo.get_lesson_by_booking_id(confirmed.id)

    assert confirmed.status == BookingStatusEnum.CONFIRMED
    assert billing_repo.reserve_calls == 1
    assert package.lessons_left == 8
    assert package.lessons_reserved == 1
    assert lessons_repo.create_calls == 1
    assert lesson is not None
    assert lesson.status == LessonStatusEnum.SCHEDULED
    assert lesson.scheduled_start_at == slot.start_at
    assert lesson.scheduled_end_at == slot.end_at
    assert any(event["event_type"] == "lesson.created" for event in audit_repo.events)


@pytest.mark.asyncio
async def test_confirm_is_idempotent_for_already_confirmed_booking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        start_at=fixed_now + timedelta(hours=36),
        end_at=fixed_now + timedelta(hours=37),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=10),
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
        confirmed_at=fixed_now - timedelta(minutes=3),
    )

    service, _, billing_repo, _, lessons_repo, audit_repo = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    confirmed = await service.confirm_booking(booking_id, actor)
    lesson = await lessons_repo.get_lesson_by_booking_id(booking_id)

    assert confirmed.id == booking_id
    assert confirmed.status == BookingStatusEnum.CONFIRMED
    assert billing_repo.reserve_calls == 0
    assert package.lessons_left == 3
    assert package.lessons_reserved == 0
    assert lessons_repo.create_calls == 1
    assert lesson is not None
    assert lesson.status == LessonStatusEnum.SCHEDULED
    assert any(event["event_type"] == "lesson.created" for event in audit_repo.events)


@pytest.mark.asyncio
async def test_confirm_rejects_past_slot_even_with_unexpired_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        start_at=fixed_now - timedelta(minutes=1),
        end_at=fixed_now + timedelta(minutes=59),
        status=SlotStatusEnum.HOLD,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=10),
        lessons_total=8,
        lessons_left=8,
    )
    booking = FakeBooking(
        id=booking_id,
        slot_id=slot_id,
        slot=slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=package_id,
        status=BookingStatusEnum.HOLD,
        hold_expires_at=fixed_now + timedelta(minutes=5),
    )

    service, _, billing_repo, _, lessons_repo, audit_repo = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    with pytest.raises(BusinessRuleException, match="Cannot confirm booking for slot in the past"):
        await service.confirm_booking(booking_id, actor)

    assert booking.status == BookingStatusEnum.HOLD
    assert billing_repo.reserve_calls == 0
    assert lessons_repo.create_calls == 0
    assert len(audit_repo.events) == 0


@pytest.mark.asyncio
async def test_confirm_requires_package_with_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    booking_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=12),
        end_at=fixed_now + timedelta(hours=13),
        status=SlotStatusEnum.HOLD,
    )
    booking = FakeBooking(
        id=booking_id,
        slot_id=slot_id,
        slot=slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=None,
        status=BookingStatusEnum.HOLD,
        hold_expires_at=fixed_now + timedelta(minutes=5),
    )

    service, _, billing_repo, _, lessons_repo, audit_repo = make_service(
        slots={slot_id: slot},
        packages={},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    with pytest.raises(BusinessRuleException, match="Booking package is required"):
        await service.confirm_booking(booking_id, actor)

    assert booking.status == BookingStatusEnum.HOLD
    assert billing_repo.reserve_calls == 0
    assert billing_repo.consume_reserved_calls == 0
    assert lessons_repo.create_calls == 0
    assert audit_repo.events == []


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
        end_at=fixed_now + timedelta(hours=26),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=8,
        lessons_left=3,
        lessons_reserved=1,
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

    service, _, billing_repo, _, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    canceled = await service.cancel_booking(booking_id, BookingCancelRequest(reason="test"), actor)

    assert canceled.status == BookingStatusEnum.CANCELED
    assert canceled.refund_returned is True
    assert billing_repo.release_calls == 1
    assert billing_repo.consume_reserved_calls == 0
    assert package.lessons_left == 3
    assert package.lessons_reserved == 0
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
        end_at=fixed_now + timedelta(hours=24),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=8,
        lessons_left=3,
        lessons_reserved=1,
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

    service, _, billing_repo, _, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    canceled = await service.cancel_booking(booking_id, BookingCancelRequest(reason="test"), actor)

    assert canceled.status == BookingStatusEnum.CANCELED
    assert canceled.refund_returned is False
    assert billing_repo.release_calls == 0
    assert billing_repo.consume_reserved_calls == 1
    assert package.lessons_left == 2
    assert package.lessons_reserved == 0
    assert slot.status == SlotStatusEnum.OPEN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("offset_seconds", "expect_refund"),
    [
        (24 * 3600 - 1, False),  # 23:59:59
        (24 * 3600, False),  # 24:00:00
        (24 * 3600 + 1, True),  # 24:00:01
    ],
)
async def test_cancel_refund_policy_boundary_cases(
    monkeypatch: pytest.MonkeyPatch,
    offset_seconds: int,
    expect_refund: bool,
) -> None:
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
        start_at=fixed_now + timedelta(seconds=offset_seconds),
        end_at=fixed_now + timedelta(seconds=offset_seconds + 3600),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=8,
        lessons_left=3,
        lessons_reserved=1,
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

    service, _, billing_repo, _, _, _ = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    canceled = await service.cancel_booking(
        booking_id,
        BookingCancelRequest(reason="boundary"),
        actor,
    )

    assert canceled.refund_returned is expect_refund
    if expect_refund:
        assert billing_repo.release_calls == 1
        assert billing_repo.consume_reserved_calls == 0
    else:
        assert billing_repo.release_calls == 0
        assert billing_repo.consume_reserved_calls == 1


@pytest.mark.asyncio
async def test_admin_cancel_writes_audit_with_refund_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    admin_id = uuid4()
    slot_id = uuid4()
    package_id = uuid4()
    booking_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=30),
        end_at=fixed_now + timedelta(hours=31),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=8,
        lessons_left=3,
        lessons_reserved=1,
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

    service, _, _, _, _, audit_repo = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    admin_actor = make_actor(admin_id, RoleEnum.ADMIN)

    canceled = await service.cancel_booking(
        booking_id,
        BookingCancelRequest(reason="Admin policy cancel"),
        admin_actor,
    )

    assert canceled.status == BookingStatusEnum.CANCELED
    assert canceled.refund_returned is True
    assert len(audit_repo.audit_logs) == 1
    log = audit_repo.audit_logs[0]
    assert log["action"] == "admin.booking.cancel"
    assert log["entity_id"] == str(booking_id)
    assert log["payload"]["booking_id"] == str(booking_id)
    assert log["payload"]["admin_id"] == str(admin_id)
    assert log["payload"]["actor_id"] == str(admin_id)
    assert log["payload"]["old_slot_id"] == str(slot_id)
    assert log["payload"]["new_slot_id"] is None
    assert log["payload"]["reason"] == "Admin policy cancel"
    assert log["payload"]["refund_returned"] is True
    assert log["payload"]["refund_policy_applied"] == "refunded"


@pytest.mark.asyncio
async def test_cancel_is_idempotent_for_already_canceled_booking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        start_at=fixed_now + timedelta(hours=36),
        end_at=fixed_now + timedelta(hours=37),
        status=SlotStatusEnum.OPEN,
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
        status=BookingStatusEnum.CANCELED,
        canceled_at=fixed_now - timedelta(hours=1),
        cancellation_reason="Initial cancel",
        refund_returned=True,
    )

    service, _, billing_repo, _, _, audit_repo = make_service(
        slots={slot_id: slot},
        packages={package_id: package},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    canceled = await service.cancel_booking(booking_id, BookingCancelRequest(reason="retry"), actor)

    assert canceled.id == booking_id
    assert canceled.status == BookingStatusEnum.CANCELED
    assert canceled.cancellation_reason == "Initial cancel"
    assert billing_repo.release_calls == 0
    assert billing_repo.consume_reserved_calls == 0
    assert len(audit_repo.events) == 0


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
        end_at=fixed_now + timedelta(hours=31),
        status=SlotStatusEnum.BOOKED,
    )
    new_slot = FakeSlot(
        id=new_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=48),
        end_at=fixed_now + timedelta(hours=49),
        status=SlotStatusEnum.OPEN,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=10,
        lessons_left=4,
        lessons_reserved=1,
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
    old_lesson = FakeLesson(
        id=uuid4(),
        booking_id=old_booking_id,
        student_id=student_id,
        teacher_id=teacher_id,
        scheduled_start_at=old_slot.start_at,
        scheduled_end_at=old_slot.end_at,
    )

    service, booking_repo, billing_repo, _, lessons_repo, audit_repo = make_service(
        slots={old_slot_id: old_slot, new_slot_id: new_slot},
        packages={package_id: package},
        bookings={old_booking_id: old_booking},
        lessons={old_booking_id: old_lesson},
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
    assert billing_repo.release_calls == 1
    assert billing_repo.reserve_calls == 1
    assert billing_repo.consume_reserved_calls == 0
    assert package.lessons_left == 4
    assert package.lessons_reserved == 1
    old_lesson_after = await lessons_repo.get_lesson_by_booking_id(old_booking_id)
    new_lesson = await lessons_repo.get_lesson_by_booking_id(new_booking.id)
    assert old_lesson_after is not None
    assert old_lesson_after.status == LessonStatusEnum.CANCELED
    assert new_lesson is not None
    assert new_lesson.status == LessonStatusEnum.SCHEDULED
    assert any(event["event_type"] == "booking.rescheduled" for event in audit_repo.events)
    assert any(event["event_type"] == "lesson.canceled" for event in audit_repo.events)
    assert any(event["event_type"] == "lesson.created" for event in audit_repo.events)


@pytest.mark.asyncio
async def test_admin_reschedule_uses_system_hold_and_writes_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    admin_id = uuid4()
    old_slot_id = uuid4()
    new_slot_id = uuid4()
    package_id = uuid4()
    old_booking_id = uuid4()

    old_slot = FakeSlot(
        id=old_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=30),
        end_at=fixed_now + timedelta(hours=31),
        status=SlotStatusEnum.BOOKED,
    )
    new_slot = FakeSlot(
        id=new_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=48),
        end_at=fixed_now + timedelta(hours=49),
        status=SlotStatusEnum.OPEN,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=10,
        lessons_left=4,
        lessons_reserved=1,
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
    old_lesson = FakeLesson(
        id=uuid4(),
        booking_id=old_booking_id,
        student_id=student_id,
        teacher_id=teacher_id,
        scheduled_start_at=old_slot.start_at,
        scheduled_end_at=old_slot.end_at,
    )

    service, booking_repo, billing_repo, _, lessons_repo, audit_repo = make_service(
        slots={old_slot_id: old_slot, new_slot_id: new_slot},
        packages={package_id: package},
        bookings={old_booking_id: old_booking},
        lessons={old_booking_id: old_lesson},
    )
    admin_actor = make_actor(admin_id, RoleEnum.ADMIN)

    new_booking = await service.reschedule_booking(
        old_booking_id,
        BookingRescheduleRequest(new_slot_id=new_slot_id, reason="Admin move"),
        admin_actor,
    )

    assert booking_repo._bookings[old_booking_id].status == BookingStatusEnum.CANCELED
    assert new_booking.status == BookingStatusEnum.CONFIRMED
    assert new_booking.rescheduled_from_booking_id == old_booking_id
    assert new_booking.student_id == student_id
    assert old_slot.status == SlotStatusEnum.OPEN
    assert new_slot.status == SlotStatusEnum.BOOKED
    assert billing_repo.release_calls == 1
    assert billing_repo.reserve_calls == 1
    assert billing_repo.consume_reserved_calls == 0
    assert package.lessons_left == 4
    assert package.lessons_reserved == 1

    old_lesson_after = await lessons_repo.get_lesson_by_booking_id(old_booking_id)
    new_lesson = await lessons_repo.get_lesson_by_booking_id(new_booking.id)
    assert old_lesson_after is not None
    assert old_lesson_after.status == LessonStatusEnum.CANCELED
    assert new_lesson is not None
    assert new_lesson.status == LessonStatusEnum.SCHEDULED

    reschedule_events = [
        event for event in audit_repo.events if event["event_type"] == "booking.rescheduled"
    ]
    assert len(reschedule_events) == 1
    assert reschedule_events[0]["payload"]["reason"] == "Admin move"

    actions = [log["action"] for log in audit_repo.audit_logs]
    assert "admin.booking.cancel" in actions
    assert "admin.booking.reschedule" in actions
    reschedule_log = next(
        log for log in audit_repo.audit_logs if log["action"] == "admin.booking.reschedule"
    )
    assert reschedule_log["payload"]["booking_id"] == str(new_booking.id)
    assert reschedule_log["payload"]["admin_id"] == str(admin_id)
    assert reschedule_log["payload"]["actor_id"] == str(admin_id)
    assert reschedule_log["payload"]["reason"] == "Admin move"
    assert reschedule_log["payload"]["old_slot_id"] == str(old_slot_id)
    assert reschedule_log["payload"]["new_slot_id"] == str(new_slot_id)


@pytest.mark.asyncio
async def test_admin_reschedule_rejects_target_slot_in_past_before_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    old_slot_id = uuid4()
    new_slot_id = uuid4()
    package_id = uuid4()
    old_booking_id = uuid4()
    admin_id = uuid4()

    old_slot = FakeSlot(
        id=old_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=30),
        end_at=fixed_now + timedelta(hours=31),
        status=SlotStatusEnum.BOOKED,
    )
    past_slot = FakeSlot(
        id=new_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now - timedelta(minutes=5),
        end_at=fixed_now + timedelta(minutes=55),
        status=SlotStatusEnum.OPEN,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=10,
        lessons_left=4,
        lessons_reserved=1,
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

    service, _, billing_repo, _, lessons_repo, audit_repo = make_service(
        slots={old_slot_id: old_slot, new_slot_id: past_slot},
        packages={package_id: package},
        bookings={old_booking_id: old_booking},
    )
    admin_actor = make_actor(admin_id, RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException, match="Cannot book a slot in the past"):
        await service.reschedule_booking(
            old_booking_id,
            BookingRescheduleRequest(new_slot_id=new_slot_id, reason="Admin move"),
            admin_actor,
        )

    assert old_booking.status == BookingStatusEnum.CONFIRMED
    assert old_slot.status == SlotStatusEnum.BOOKED
    assert past_slot.status == SlotStatusEnum.OPEN
    assert billing_repo.release_calls == 0
    assert billing_repo.reserve_calls == 0
    assert billing_repo.consume_reserved_calls == 0
    assert lessons_repo.create_calls == 0
    assert audit_repo.events == []
    assert audit_repo.audit_logs == []


@pytest.mark.asyncio
async def test_reschedule_returns_existing_successor_on_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    old_slot_id = uuid4()
    new_slot_id = uuid4()
    package_id = uuid4()
    old_booking_id = uuid4()
    new_booking_id = uuid4()

    old_slot = FakeSlot(
        id=old_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=30),
        end_at=fixed_now + timedelta(hours=31),
        status=SlotStatusEnum.OPEN,
    )
    new_slot = FakeSlot(
        id=new_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=48),
        end_at=fixed_now + timedelta(hours=49),
        status=SlotStatusEnum.BOOKED,
    )
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now + timedelta(days=7),
        lessons_total=10,
        lessons_left=4,
        lessons_reserved=1,
    )
    old_booking = FakeBooking(
        id=old_booking_id,
        slot_id=old_slot_id,
        slot=old_slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=package_id,
        status=BookingStatusEnum.CANCELED,
        canceled_at=fixed_now - timedelta(minutes=10),
        cancellation_reason="Rescheduled by user",
        refund_returned=True,
    )
    new_booking = FakeBooking(
        id=new_booking_id,
        slot_id=new_slot_id,
        slot=new_slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=package_id,
        status=BookingStatusEnum.CONFIRMED,
        confirmed_at=fixed_now - timedelta(minutes=8),
        rescheduled_from_booking_id=old_booking_id,
    )

    service, booking_repo, billing_repo, _, _, audit_repo = make_service(
        slots={old_slot_id: old_slot, new_slot_id: new_slot},
        packages={package_id: package},
        bookings={old_booking_id: old_booking, new_booking_id: new_booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    retried = await service.reschedule_booking(
        old_booking_id,
        BookingRescheduleRequest(new_slot_id=new_slot_id),
        actor,
    )

    assert retried.id == new_booking_id
    assert retried.rescheduled_from_booking_id == old_booking_id
    assert billing_repo.release_calls == 0
    assert billing_repo.reserve_calls == 0
    assert billing_repo.consume_reserved_calls == 0
    assert len(booking_repo._bookings) == 2
    assert len(audit_repo.events) == 0


@pytest.mark.asyncio
async def test_list_teacher_students_with_packages_requires_teacher_role() -> None:
    service, _, _, _, _, _ = make_service(
        slots={},
        packages={},
        teacher_students_with_packages=([], 0),
    )
    actor = make_actor(uuid4(), RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException, match="Only teacher can list own students"):
        await service.list_teacher_students_with_packages(actor, limit=20, offset=0)


@pytest.mark.asyncio
async def test_list_teacher_students_with_packages_returns_repository_payload() -> None:
    teacher_id = uuid4()
    student_id = uuid4()
    package_id = uuid4()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=UTC)
    payload = [
        {
            "student_id": student_id,
            "student_email": "student@example.com",
            "student_full_name": "Student Example",
            "active_bookings_count": 2,
            "last_booking_at": now,
            "packages": [
                {
                    "package_id": package_id,
                    "status": PackageStatusEnum.ACTIVE,
                    "lessons_total": 8,
                    "lessons_left": 6,
                    "lessons_reserved": 1,
                    "lessons_available": 5,
                    "expires_at": now + timedelta(days=30),
                },
            ],
        },
    ]
    service, _, _, _, _, _ = make_service(
        slots={},
        packages={},
        teacher_students_with_packages=(payload, 1),
    )
    actor = make_actor(teacher_id, RoleEnum.TEACHER)

    items, total = await service.list_teacher_students_with_packages(actor, limit=20, offset=0)

    assert total == 1
    assert len(items) == 1
    assert items[0].student_id == student_id
    assert items[0].active_bookings_count == 2
    assert len(items[0].packages) == 1
    assert items[0].packages[0].package_id == package_id
    assert items[0].packages[0].lessons_available == 5


@pytest.mark.asyncio
async def test_expire_holds_requires_admin_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    slot_id = uuid4()
    booking_id = uuid4()

    slot = FakeSlot(
        id=slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=24),
        end_at=fixed_now + timedelta(hours=25),
        status=SlotStatusEnum.HOLD,
    )
    booking = FakeBooking(
        id=booking_id,
        slot_id=slot_id,
        slot=slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=uuid4(),
        status=BookingStatusEnum.HOLD,
        hold_expires_at=fixed_now - timedelta(minutes=1),
    )

    service, _, _, _, _, _ = make_service(
        slots={slot_id: slot},
        packages={},
        bookings={booking_id: booking},
    )
    actor = make_actor(student_id, RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.expire_holds(actor)


@pytest.mark.asyncio
async def test_expire_holds_system_expires_only_stale_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(booking_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    teacher_id = uuid4()
    stale_slot_id = uuid4()
    fresh_slot_id = uuid4()
    stale_booking_id = uuid4()
    fresh_booking_id = uuid4()

    stale_slot = FakeSlot(
        id=stale_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=24),
        end_at=fixed_now + timedelta(hours=25),
        status=SlotStatusEnum.HOLD,
    )
    fresh_slot = FakeSlot(
        id=fresh_slot_id,
        teacher_id=teacher_id,
        start_at=fixed_now + timedelta(hours=26),
        end_at=fixed_now + timedelta(hours=27),
        status=SlotStatusEnum.HOLD,
    )
    stale_booking = FakeBooking(
        id=stale_booking_id,
        slot_id=stale_slot_id,
        slot=stale_slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=uuid4(),
        status=BookingStatusEnum.HOLD,
        hold_expires_at=fixed_now - timedelta(minutes=2),
    )
    fresh_booking = FakeBooking(
        id=fresh_booking_id,
        slot_id=fresh_slot_id,
        slot=fresh_slot,
        student_id=student_id,
        teacher_id=teacher_id,
        package_id=uuid4(),
        status=BookingStatusEnum.HOLD,
        hold_expires_at=fixed_now + timedelta(minutes=2),
    )

    service, _, _, _, _, audit_repo = make_service(
        slots={stale_slot_id: stale_slot, fresh_slot_id: fresh_slot},
        packages={},
        bookings={stale_booking_id: stale_booking, fresh_booking_id: fresh_booking},
    )

    expired_count = await service.expire_holds_system()

    assert expired_count == 1
    assert stale_booking.status == BookingStatusEnum.EXPIRED
    assert stale_booking.hold_expires_at is None
    assert stale_slot.status == SlotStatusEnum.OPEN
    assert fresh_booking.status == BookingStatusEnum.HOLD
    assert fresh_slot.status == SlotStatusEnum.HOLD
    assert any(
        event["event_type"] == "booking.hold.expired"
        and event["payload"]["booking_id"] == str(stale_booking_id)
        for event in audit_repo.events
    )
