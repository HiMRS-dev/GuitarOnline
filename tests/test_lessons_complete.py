from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import app.modules.lessons.service as lessons_service_module
from app.core.enums import LessonStatusEnum, RoleEnum
from app.modules.lessons.service import LessonsService
from app.shared.exceptions import ConflictException, NotFoundException, UnauthorizedException


@dataclass
class FakeLesson:
    id: UUID
    booking_id: UUID
    student_id: UUID
    teacher_id: UUID
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    status: LessonStatusEnum
    consumed_at: datetime | None = None


@dataclass
class FakeBooking:
    id: UUID
    package_id: UUID | None


@dataclass
class FakePackage:
    id: UUID
    lessons_left: int
    lessons_reserved: int


class FakeLessonsRepository:
    def __init__(self, lessons: dict[UUID, FakeLesson]) -> None:
        self.lessons = lessons
        self.update_calls = 0

    async def get_lesson_by_id(self, lesson_id: UUID) -> FakeLesson | None:
        return self.lessons.get(lesson_id)

    async def update_lesson(self, lesson: FakeLesson, **changes) -> FakeLesson:
        for key, value in changes.items():
            if value is not None:
                setattr(lesson, key, value)
        self.update_calls += 1
        return lesson


class FakeBookingRepository:
    def __init__(self, bookings: dict[UUID, FakeBooking]) -> None:
        self.bookings = bookings

    async def get_booking_by_id(self, booking_id: UUID) -> FakeBooking | None:
        return self.bookings.get(booking_id)


class FakeBillingRepository:
    def __init__(self, packages: dict[UUID, FakePackage]) -> None:
        self.packages = packages
        self.consume_calls = 0

    async def get_package_by_id(self, package_id: UUID) -> FakePackage | None:
        return self.packages.get(package_id)

    async def consume_reserved_package_lesson(self, package: FakePackage) -> None:
        if package.lessons_reserved <= 0:
            return
        package.lessons_reserved -= 1
        package.lessons_left -= 1
        self.consume_calls += 1


def make_actor(role: RoleEnum, *, actor_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=actor_id or uuid4(), role=SimpleNamespace(name=role))


def make_lesson(*, status: LessonStatusEnum, teacher_id: UUID, booking_id: UUID) -> FakeLesson:
    now = datetime(2026, 3, 6, 10, 0, tzinfo=UTC)
    return FakeLesson(
        id=uuid4(),
        booking_id=booking_id,
        student_id=uuid4(),
        teacher_id=teacher_id,
        scheduled_start_at=now + timedelta(hours=1),
        scheduled_end_at=now + timedelta(hours=2),
        status=status,
    )


def make_service(
    *,
    lesson: FakeLesson,
    booking_id: UUID | None,
    package_id: UUID | None,
    package: FakePackage | None,
) -> LessonsService:
    bookings = (
        {booking_id: FakeBooking(id=booking_id, package_id=package_id)}
        if booking_id is not None
        else {}
    )
    packages = {package_id: package} if package_id is not None and package is not None else {}
    return LessonsService(
        repository=FakeLessonsRepository({lesson.id: lesson}),  # type: ignore[arg-type]
        billing_repository=FakeBillingRepository(packages),  # type: ignore[arg-type]
        booking_repository=FakeBookingRepository(bookings),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_complete_lesson_teacher_owns_lesson_and_consumes_reserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 3, 6, 11, 0, tzinfo=UTC)
    monkeypatch.setattr(lessons_service_module, "utc_now", lambda: fixed_now)

    teacher_id = uuid4()
    booking_id = uuid4()
    package_id = uuid4()
    lesson = make_lesson(
        status=LessonStatusEnum.SCHEDULED,
        teacher_id=teacher_id,
        booking_id=booking_id,
    )
    package = FakePackage(id=package_id, lessons_left=5, lessons_reserved=1)

    service = make_service(
        lesson=lesson,
        booking_id=booking_id,
        package_id=package_id,
        package=package,
    )
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    completed = await service.complete_lesson(lesson.id, teacher)

    assert completed.status == LessonStatusEnum.COMPLETED
    assert completed.consumed_at == fixed_now
    assert package.lessons_left == 4
    assert package.lessons_reserved == 0


@pytest.mark.asyncio
async def test_complete_lesson_is_idempotent_on_repeated_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 3, 6, 11, 0, tzinfo=UTC)
    monkeypatch.setattr(lessons_service_module, "utc_now", lambda: fixed_now)

    teacher_id = uuid4()
    booking_id = uuid4()
    package_id = uuid4()
    lesson = make_lesson(
        status=LessonStatusEnum.SCHEDULED,
        teacher_id=teacher_id,
        booking_id=booking_id,
    )
    package = FakePackage(id=package_id, lessons_left=5, lessons_reserved=1)
    service = make_service(
        lesson=lesson,
        booking_id=booking_id,
        package_id=package_id,
        package=package,
    )
    billing_repo = service.billing_repository
    assert billing_repo is not None
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    first = await service.complete_lesson(lesson.id, teacher)
    second = await service.complete_lesson(lesson.id, teacher)

    assert first.status == LessonStatusEnum.COMPLETED
    assert second.status == LessonStatusEnum.COMPLETED
    assert first.consumed_at == fixed_now
    assert second.consumed_at == fixed_now
    assert package.lessons_left == 4
    assert package.lessons_reserved == 0
    assert billing_repo.consume_calls == 1


@pytest.mark.asyncio
async def test_complete_lesson_is_idempotent_when_already_completed_with_consumed_at() -> None:
    teacher_id = uuid4()
    booking_id = uuid4()
    package_id = uuid4()
    consumed_at = datetime(2026, 3, 6, 11, 0, tzinfo=UTC)
    lesson = make_lesson(
        status=LessonStatusEnum.COMPLETED,
        teacher_id=teacher_id,
        booking_id=booking_id,
    )
    lesson.consumed_at = consumed_at
    package = FakePackage(id=package_id, lessons_left=4, lessons_reserved=0)
    service = make_service(
        lesson=lesson,
        booking_id=booking_id,
        package_id=package_id,
        package=package,
    )
    billing_repo = service.billing_repository
    assert billing_repo is not None
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    completed = await service.complete_lesson(lesson.id, teacher)

    assert completed.status == LessonStatusEnum.COMPLETED
    assert completed.consumed_at == consumed_at
    assert billing_repo.consume_calls == 0


@pytest.mark.asyncio
async def test_complete_lesson_rejects_non_scheduled_status() -> None:
    teacher_id = uuid4()
    booking_id = uuid4()
    package_id = uuid4()
    lesson = make_lesson(
        status=LessonStatusEnum.CANCELED,
        teacher_id=teacher_id,
        booking_id=booking_id,
    )
    package = FakePackage(id=package_id, lessons_left=5, lessons_reserved=1)

    service = make_service(
        lesson=lesson,
        booking_id=booking_id,
        package_id=package_id,
        package=package,
    )
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    with pytest.raises(ConflictException, match="Only scheduled lesson can be completed"):
        await service.complete_lesson(lesson.id, teacher)


@pytest.mark.asyncio
async def test_complete_lesson_requires_admin_or_teacher_role() -> None:
    teacher_id = uuid4()
    booking_id = uuid4()
    package_id = uuid4()
    lesson = make_lesson(
        status=LessonStatusEnum.SCHEDULED,
        teacher_id=teacher_id,
        booking_id=booking_id,
    )
    package = FakePackage(id=package_id, lessons_left=5, lessons_reserved=1)

    service = make_service(
        lesson=lesson,
        booking_id=booking_id,
        package_id=package_id,
        package=package,
    )
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException, match="Only admin or teacher can complete lessons"):
        await service.complete_lesson(lesson.id, student)


@pytest.mark.asyncio
async def test_complete_lesson_teacher_cannot_complete_foreign_lesson() -> None:
    booking_id = uuid4()
    package_id = uuid4()
    lesson = make_lesson(
        status=LessonStatusEnum.SCHEDULED,
        teacher_id=uuid4(),
        booking_id=booking_id,
    )
    package = FakePackage(id=package_id, lessons_left=5, lessons_reserved=1)

    service = make_service(
        lesson=lesson,
        booking_id=booking_id,
        package_id=package_id,
        package=package,
    )
    other_teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException, match="Teacher can complete only own lessons"):
        await service.complete_lesson(lesson.id, other_teacher)


@pytest.mark.asyncio
async def test_complete_lesson_raises_not_found_when_booking_missing() -> None:
    teacher_id = uuid4()
    booking_id = uuid4()
    lesson = make_lesson(
        status=LessonStatusEnum.SCHEDULED,
        teacher_id=teacher_id,
        booking_id=booking_id,
    )

    service = make_service(
        lesson=lesson,
        booking_id=None,
        package_id=None,
        package=None,
    )
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    with pytest.raises(NotFoundException, match="Booking not found"):
        await service.complete_lesson(lesson.id, teacher)
