from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import LessonStatusEnum, RoleEnum
from app.modules.lessons.schemas import TeacherLessonReportRequest
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
    notes: str | None = None
    homework: str | None = None
    links: list[str] | None = None
    meeting_url: str | None = None
    recording_url: str | None = None


class FakeLessonsRepository:
    def __init__(self, lesson: FakeLesson) -> None:
        self.lesson = lesson

    async def get_lesson_by_id(self, lesson_id: UUID) -> FakeLesson | None:
        if lesson_id == self.lesson.id:
            return self.lesson
        return None

    async def update_lesson(self, lesson: FakeLesson, **changes) -> FakeLesson:
        for key, value in changes.items():
            if value is not None:
                setattr(lesson, key, value)
        return lesson


class FakeAuditRepository:
    def __init__(self) -> None:
        self.logs: list[dict] = []

    async def create_audit_log(
        self,
        actor_id,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict,
    ) -> None:
        self.logs.append(
            {
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload,
            },
        )


def make_actor(role: RoleEnum, *, actor_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=actor_id or uuid4(), role=SimpleNamespace(name=role))


def make_lesson(*, teacher_id: UUID) -> FakeLesson:
    now = datetime(2026, 3, 7, 22, 0, tzinfo=UTC)
    return FakeLesson(
        id=uuid4(),
        booking_id=uuid4(),
        student_id=uuid4(),
        teacher_id=teacher_id,
        scheduled_start_at=now + timedelta(hours=1),
        scheduled_end_at=now + timedelta(hours=2),
        status=LessonStatusEnum.SCHEDULED,
        notes="Old notes",
    )


@pytest.mark.asyncio
async def test_report_update_writes_audit_with_changed_fields_only() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    audit_repo = FakeAuditRepository()
    service = LessonsService(
        repository=FakeLessonsRepository(lesson),  # type: ignore[arg-type]
        audit_repository=audit_repo,  # type: ignore[arg-type]
    )
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    await service.report_lesson(
        lesson.id,
        TeacherLessonReportRequest(
            notes="Updated notes",
            homework="Practice arpeggios",
            links=["https://example.com/a"],
        ),
        teacher,
    )

    assert len(audit_repo.logs) == 1
    log = audit_repo.logs[0]
    assert log["action"] == "lesson.report.update"
    assert log["entity_type"] == "lesson"
    assert log["entity_id"] == str(lesson.id)
    assert log["payload"]["lesson_id"] == str(lesson.id)
    assert set(log["payload"]["changed_fields"]) == {"notes", "homework", "links"}
    assert log["payload"]["changed_count"] == 3
    assert "notes" not in {key for key in log["payload"] if key.startswith("new_")}


@pytest.mark.asyncio
async def test_report_update_does_not_write_audit_when_nothing_changed() -> None:
    teacher_id = uuid4()
    lesson = make_lesson(teacher_id=teacher_id)
    lesson.homework = "Already set"
    lesson.links = ["https://example.com/a"]
    audit_repo = FakeAuditRepository()
    service = LessonsService(
        repository=FakeLessonsRepository(lesson),  # type: ignore[arg-type]
        audit_repository=audit_repo,  # type: ignore[arg-type]
    )
    teacher = make_actor(RoleEnum.TEACHER, actor_id=teacher_id)

    await service.report_lesson(
        lesson.id,
        TeacherLessonReportRequest(
            notes="Old notes",
            homework="Already set",
            links=["https://example.com/a"],
        ),
        teacher,
    )

    assert audit_repo.logs == []
