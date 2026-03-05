from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

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


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_lesson(status: LessonStatusEnum) -> FakeLesson:
    now = datetime(2026, 3, 5, 10, 0, tzinfo=UTC)
    return FakeLesson(
        id=uuid4(),
        booking_id=uuid4(),
        student_id=uuid4(),
        teacher_id=uuid4(),
        scheduled_start_at=now + timedelta(hours=24),
        scheduled_end_at=now + timedelta(hours=25),
        status=status,
    )


@pytest.mark.asyncio
async def test_mark_no_show_changes_scheduled_lesson_status() -> None:
    lesson = make_lesson(LessonStatusEnum.SCHEDULED)
    repository = FakeLessonsRepository({lesson.id: lesson})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.mark_no_show(lesson.id, admin)

    assert updated.status == LessonStatusEnum.NO_SHOW
    assert repository.update_calls == 1


@pytest.mark.asyncio
async def test_mark_no_show_is_idempotent_for_no_show_status() -> None:
    lesson = make_lesson(LessonStatusEnum.NO_SHOW)
    repository = FakeLessonsRepository({lesson.id: lesson})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.mark_no_show(lesson.id, admin)

    assert updated.status == LessonStatusEnum.NO_SHOW
    assert repository.update_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [LessonStatusEnum.COMPLETED, LessonStatusEnum.CANCELED])
async def test_mark_no_show_rejects_terminal_non_scheduled_statuses(
    status: LessonStatusEnum,
) -> None:
    lesson = make_lesson(status)
    repository = FakeLessonsRepository({lesson.id: lesson})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(ConflictException, match="Only scheduled lesson can be marked as no-show"):
        await service.mark_no_show(lesson.id, admin)

    assert repository.update_calls == 0


@pytest.mark.asyncio
async def test_mark_no_show_requires_admin_role() -> None:
    lesson = make_lesson(LessonStatusEnum.SCHEDULED)
    repository = FakeLessonsRepository({lesson.id: lesson})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException, match="Only admin can mark lesson as no-show"):
        await service.mark_no_show(lesson.id, teacher)

    assert repository.update_calls == 0


@pytest.mark.asyncio
async def test_mark_no_show_raises_not_found_for_missing_lesson() -> None:
    repository = FakeLessonsRepository({})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(NotFoundException, match="Lesson not found"):
        await service.mark_no_show(uuid4(), admin)

    assert repository.update_calls == 0
