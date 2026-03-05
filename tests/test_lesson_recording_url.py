from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.core.enums import LessonStatusEnum, RoleEnum
from app.modules.lessons.schemas import LessonUpdate, TeacherLessonReportRequest
from app.modules.lessons.service import LessonsService


@dataclass
class FakeLesson:
    id: UUID
    booking_id: UUID
    student_id: UUID
    teacher_id: UUID
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    status: LessonStatusEnum
    recording_url: str | None = None


class FakeLessonsRepository:
    def __init__(self, lessons: dict[UUID, FakeLesson]) -> None:
        self.lessons = lessons

    async def get_lesson_by_id(self, lesson_id: UUID) -> FakeLesson | None:
        return self.lessons.get(lesson_id)

    async def update_lesson(self, lesson: FakeLesson, **changes) -> FakeLesson:
        for key, value in changes.items():
            if value is not None:
                setattr(lesson, key, value)
        return lesson


def make_actor(role: RoleEnum, *, actor_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=actor_id or uuid4(), role=SimpleNamespace(name=role))


def make_lesson(*, teacher_id: UUID) -> FakeLesson:
    now = datetime(2026, 3, 7, 16, 0, tzinfo=UTC)
    return FakeLesson(
        id=uuid4(),
        booking_id=uuid4(),
        student_id=uuid4(),
        teacher_id=teacher_id,
        scheduled_start_at=now + timedelta(hours=1),
        scheduled_end_at=now + timedelta(hours=2),
        status=LessonStatusEnum.SCHEDULED,
    )


@pytest.mark.asyncio
async def test_update_lesson_supports_recording_url() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    service = LessonsService(repository=FakeLessonsRepository({lesson.id: lesson}))  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    updated = await service.update_lesson(
        lesson.id,
        LessonUpdate(recording_url="https://video.example.com/r/lesson-1"),
        teacher,
    )

    assert updated.recording_url == "https://video.example.com/r/lesson-1"


@pytest.mark.asyncio
async def test_teacher_report_supports_recording_url() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    service = LessonsService(repository=FakeLessonsRepository({lesson.id: lesson}))  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    updated = await service.report_lesson(
        lesson.id,
        TeacherLessonReportRequest(recording_url="https://video.example.com/r/lesson-2"),
        teacher,
    )

    assert updated.recording_url == "https://video.example.com/r/lesson-2"


def test_recording_url_requires_valid_url_format() -> None:
    with pytest.raises(ValidationError):
        LessonUpdate(recording_url="not-a-url")

    with pytest.raises(ValidationError):
        TeacherLessonReportRequest(recording_url="not-a-url")
