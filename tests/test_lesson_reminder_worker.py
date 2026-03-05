from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.enums import NotificationStatusEnum, NotificationTemplateKeyEnum
from app.modules.notifications.reminder_worker import LessonReminder24hWorker


@dataclass
class FakeLesson:
    id: UUID
    student_id: UUID
    scheduled_start_at: datetime


@dataclass
class FakeNotification:
    id: UUID
    user_id: UUID
    channel: str
    template_key: str | None
    title: str
    body: str
    idempotency_key: str | None
    status: NotificationStatusEnum = NotificationStatusEnum.PENDING
    sent_at: datetime | None = None


class FakeLessonsRepository:
    def __init__(self, lessons: list[FakeLesson]) -> None:
        self.lessons = lessons
        self.calls: list[dict[str, object]] = []

    async def list_scheduled_lessons_starting_between(
        self,
        *,
        from_utc,
        to_utc,
        limit: int,
    ) -> list[FakeLesson]:
        self.calls.append(
            {
                "from_utc": from_utc,
                "to_utc": to_utc,
                "limit": limit,
            },
        )
        return self.lessons


class FakeNotificationsRepository:
    def __init__(self, existing_keys: set[str] | None = None) -> None:
        self.existing_keys = existing_keys or set()
        self.created: list[FakeNotification] = []

    async def get_by_idempotency_key(self, idempotency_key: str) -> FakeNotification | None:
        if idempotency_key in self.existing_keys:
            return FakeNotification(
                id=uuid4(),
                user_id=uuid4(),
                channel="email",
                template_key=NotificationTemplateKeyEnum.LESSON_REMINDER_24H.value,
                title="Lesson reminder",
                body="existing",
                idempotency_key=idempotency_key,
            )
        return None

    async def create_notification(
        self,
        user_id: UUID,
        channel: str,
        template_key: str | None,
        title: str,
        body: str,
        idempotency_key: str | None = None,
    ) -> FakeNotification:
        notification = FakeNotification(
            id=uuid4(),
            user_id=user_id,
            channel=channel,
            template_key=template_key,
            title=title,
            body=body,
            idempotency_key=idempotency_key,
        )
        self.created.append(notification)
        return notification

    async def set_status(
        self,
        notification: FakeNotification,
        status: NotificationStatusEnum,
        sent_at: datetime | None,
    ) -> FakeNotification:
        notification.status = status
        notification.sent_at = sent_at
        return notification


@pytest.mark.asyncio
async def test_reminder_worker_generates_reminder_and_skips_duplicate_by_idempotency_key() -> None:
    now_point = datetime(2026, 3, 6, 9, 0, tzinfo=UTC)
    duplicate_lesson = FakeLesson(
        id=uuid4(),
        student_id=uuid4(),
        scheduled_start_at=now_point + timedelta(hours=2),
    )
    new_lesson = FakeLesson(
        id=uuid4(),
        student_id=uuid4(),
        scheduled_start_at=now_point + timedelta(hours=3),
    )
    duplicate_key = LessonReminder24hWorker.build_idempotency_key(
        duplicate_lesson.id,
        duplicate_lesson.scheduled_start_at.date().isoformat(),
    )

    lessons_repo = FakeLessonsRepository([duplicate_lesson, new_lesson])
    notifications_repo = FakeNotificationsRepository(existing_keys={duplicate_key})
    worker = LessonReminder24hWorker(
        lessons_repository=lessons_repo,  # type: ignore[arg-type]
        notifications_repository=notifications_repo,  # type: ignore[arg-type]
        batch_size=10,
        now_provider=lambda: now_point,
    )

    stats = await worker.run_once()

    assert stats == {"scanned": 2, "created": 1, "skipped": 1}
    assert lessons_repo.calls == [
        {
            "from_utc": now_point,
            "to_utc": now_point + timedelta(hours=24),
            "limit": 10,
        },
    ]
    assert len(notifications_repo.created) == 1
    created = notifications_repo.created[0]
    assert created.user_id == new_lesson.student_id
    assert created.template_key == NotificationTemplateKeyEnum.LESSON_REMINDER_24H.value
    assert created.status == NotificationStatusEnum.SENT
    assert created.idempotency_key == LessonReminder24hWorker.build_idempotency_key(
        new_lesson.id,
        new_lesson.scheduled_start_at.date().isoformat(),
    )
