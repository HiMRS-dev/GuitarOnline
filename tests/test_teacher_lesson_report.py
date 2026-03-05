from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import LessonStatusEnum, RoleEnum
from app.modules.lessons.schemas import TeacherLessonReportRequest
from app.modules.lessons.service import LessonsService
from app.shared.exceptions import NotFoundException, UnauthorizedException


@dataclass
class FakeLesson:
    id: UUID
    booking_id: UUID
    student_id: UUID
    teacher_id: UUID
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    status: LessonStatusEnum
    notes: str | None = None
    homework: str | None = None
    links: list[str] | None = None


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


def make_actor(role: RoleEnum, actor_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=actor_id or uuid4(), role=SimpleNamespace(name=role))


def make_lesson(teacher_id: UUID) -> FakeLesson:
    now = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
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
async def test_teacher_can_report_own_lesson_and_store_links() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    repository = FakeLessonsRepository({lesson.id: lesson})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, teacher_id)

    updated = await service.report_lesson(
        lesson.id,
        TeacherLessonReportRequest(
            notes="Scales progress",
            homework="Practice pentatonic pattern A",
            links=["https://example.com/lesson-note"],
        ),
        teacher,
    )

    assert updated.notes == "Scales progress"
    assert updated.homework == "Practice pentatonic pattern A"
    assert updated.links == ["https://example.com/lesson-note"]
    assert repository.update_calls == 1


@pytest.mark.asyncio
async def test_teacher_report_requires_teacher_role() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    repository = FakeLessonsRepository({lesson.id: lesson})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException, match="Only teacher can report lesson"):
        await service.report_lesson(
            lesson.id,
            TeacherLessonReportRequest(notes="x", homework="y", links=[]),
            student,
        )

    assert repository.update_calls == 0


@pytest.mark.asyncio
async def test_teacher_report_rejects_foreign_lesson() -> None:
    lesson = make_lesson(teacher_id=uuid4())
    repository = FakeLessonsRepository({lesson.id: lesson})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    other_teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException, match="Teacher can report only own lessons"):
        await service.report_lesson(
            lesson.id,
            TeacherLessonReportRequest(notes="x", homework="y", links=[]),
            other_teacher,
        )

    assert repository.update_calls == 0


@pytest.mark.asyncio
async def test_teacher_report_raises_not_found_for_missing_lesson() -> None:
    repository = FakeLessonsRepository({})
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(NotFoundException, match="Lesson not found"):
        await service.report_lesson(
            uuid4(),
            TeacherLessonReportRequest(notes="x", homework="y", links=[]),
            teacher,
        )
