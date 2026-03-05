from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import app.modules.lessons.service as lessons_service_module
from app.core.enums import LessonStatusEnum, RoleEnum
from app.modules.lessons.schemas import LessonUpdate, TeacherLessonReportRequest
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
    meeting_url: str | None = None


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
    now = datetime(2026, 3, 7, 14, 0, tzinfo=UTC)
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
async def test_update_lesson_supports_manual_meeting_url() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    service = LessonsService(repository=FakeLessonsRepository({lesson.id: lesson}))  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    updated = await service.update_lesson(
        lesson.id,
        LessonUpdate(meeting_url="https://meet.example.com/manual-room"),
        teacher,
    )

    assert updated.meeting_url == "https://meet.example.com/manual-room"


@pytest.mark.asyncio
async def test_report_lesson_can_generate_meeting_url_from_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    service = LessonsService(repository=FakeLessonsRepository({lesson.id: lesson}))  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)
    monkeypatch.setattr(
        lessons_service_module.settings,
        "lesson_meeting_url_template",
        "https://meet.example.com/lesson/{lesson_id}?booking={booking_id}",
    )

    updated = await service.report_lesson(
        lesson.id,
        TeacherLessonReportRequest(use_meeting_url_template=True),
        teacher,
    )

    assert updated.meeting_url is not None
    assert str(lesson.id) in updated.meeting_url
    assert str(lesson.booking_id) in updated.meeting_url


@pytest.mark.asyncio
async def test_template_generation_requires_config(monkeypatch: pytest.MonkeyPatch) -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    service = LessonsService(repository=FakeLessonsRepository({lesson.id: lesson}))  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)
    monkeypatch.setattr(lessons_service_module.settings, "lesson_meeting_url_template", None)

    with pytest.raises(BusinessRuleException, match="Meeting URL template is not configured"):
        await service.report_lesson(
            lesson.id,
            TeacherLessonReportRequest(use_meeting_url_template=True),
            teacher,
        )


@pytest.mark.asyncio
async def test_meeting_url_rejects_manual_and_template_mode_together() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    service = LessonsService(repository=FakeLessonsRepository({lesson.id: lesson}))  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    with pytest.raises(
        BusinessRuleException,
        match="Provide either meeting_url or use_meeting_url_template, not both",
    ):
        await service.update_lesson(
            lesson.id,
            LessonUpdate(
                meeting_url="https://meet.example.com/manual-room",
                use_meeting_url_template=True,
            ),
            teacher,
        )
