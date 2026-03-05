from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import LessonStatusEnum, RoleEnum
from app.modules.lessons.schemas import TeacherLessonReportRequest
from app.modules.lessons.service import LessonsService
from app.shared.exceptions import BusinessRuleException


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
    def __init__(self, lesson: FakeLesson) -> None:
        self.lesson = lesson
        self.update_calls = 0

    async def get_lesson_by_id(self, lesson_id: UUID) -> FakeLesson | None:
        if lesson_id == self.lesson.id:
            return self.lesson
        return None

    async def update_lesson(self, lesson: FakeLesson, **changes) -> FakeLesson:
        for key, value in changes.items():
            if value is not None:
                setattr(lesson, key, value)
        self.update_calls += 1
        return lesson


def make_actor(role: RoleEnum, *, actor_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=actor_id or uuid4(), role=SimpleNamespace(name=role))


def make_lesson(teacher_id: UUID) -> FakeLesson:
    now = datetime(2026, 3, 7, 19, 0, tzinfo=UTC)
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
async def test_report_moderation_accepts_clean_payload() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id)
    repository = FakeLessonsRepository(lesson)
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    updated = await service.report_lesson(
        lesson.id,
        TeacherLessonReportRequest(
            notes="Solid rhythm control today",
            homework="Practice scales with metronome",
            links=["https://example.com/materials/scale-sheet"],
        ),
        teacher,
    )

    assert updated.notes is not None
    assert repository.update_calls == 1


@pytest.mark.asyncio
async def test_report_moderation_rejects_email_in_notes() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id)
    repository = FakeLessonsRepository(lesson)
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    with pytest.raises(BusinessRuleException, match="restricted contact information"):
        await service.report_lesson(
            lesson.id,
            TeacherLessonReportRequest(
                notes="Send task to student@mail.com",
                homework="Practice",
                links=[],
            ),
            teacher,
        )

    assert repository.update_calls == 0


@pytest.mark.asyncio
async def test_report_moderation_rejects_phone_in_homework() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id)
    repository = FakeLessonsRepository(lesson)
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    with pytest.raises(BusinessRuleException, match="restricted contact information"):
        await service.report_lesson(
            lesson.id,
            TeacherLessonReportRequest(
                notes="Keep timing stable",
                homework="Call +1 (555) 123-4567 for details",
                links=[],
            ),
            teacher,
        )

    assert repository.update_calls == 0


@pytest.mark.asyncio
async def test_report_moderation_rejects_contact_link() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id)
    repository = FakeLessonsRepository(lesson)
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    with pytest.raises(BusinessRuleException, match="restricted contact information"):
        await service.report_lesson(
            lesson.id,
            TeacherLessonReportRequest(
                notes="Review chord transitions",
                homework="Practice 20 min",
                links=["https://t.me/somechannel"],
            ),
            teacher,
        )

    assert repository.update_calls == 0
