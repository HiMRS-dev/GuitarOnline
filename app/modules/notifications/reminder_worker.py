"""Lesson reminder worker for upcoming 24h lessons."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from app.core.enums import NotificationStatusEnum, NotificationTemplateKeyEnum
from app.modules.lessons.repository import LessonsRepository
from app.modules.notifications.repository import NotificationsRepository
from app.modules.notifications.templates import render_template
from app.shared.utils import utc_now


class LessonReminder24hWorker:
    """Generate reminder notifications for lessons starting in the next 24 hours."""

    def __init__(
        self,
        lessons_repository: LessonsRepository,
        notifications_repository: NotificationsRepository,
        *,
        batch_size: int = 500,
        window_hours: int = 24,
        now_provider=utc_now,
    ) -> None:
        self.lessons_repository = lessons_repository
        self.notifications_repository = notifications_repository
        self.batch_size = batch_size
        self.window_hours = window_hours
        self.now_provider = now_provider

    @staticmethod
    def build_idempotency_key(lesson_id: UUID, reminder_date: str) -> str:
        """Build deterministic key for one reminder per lesson/date."""
        return f"lesson:{lesson_id}:lesson_reminder_24h:{reminder_date}"

    async def run_once(self) -> dict[str, int]:
        """Generate reminder notifications and return cycle stats."""
        cycle_now = self.now_provider()
        reminder_window_end = cycle_now + timedelta(hours=self.window_hours)
        lessons = await self.lessons_repository.list_scheduled_lessons_starting_between(
            from_utc=cycle_now,
            to_utc=reminder_window_end,
            limit=self.batch_size,
        )

        stats = {"scanned": len(lessons), "created": 0, "skipped": 0}
        for lesson in lessons:
            reminder_date = lesson.scheduled_start_at.date().isoformat()
            idempotency_key = self.build_idempotency_key(lesson.id, reminder_date)
            existing = await self.notifications_repository.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                stats["skipped"] += 1
                continue

            rendered = render_template(
                NotificationTemplateKeyEnum.LESSON_REMINDER_24H,
                {
                    "lesson_id": str(lesson.id),
                    "lesson_start_at_utc": lesson.scheduled_start_at.isoformat(),
                },
            )
            notification = await self.notifications_repository.create_notification(
                user_id=lesson.student_id,
                channel="email",
                template_key=rendered.template_key.value,
                title=rendered.title,
                body=rendered.body,
                idempotency_key=idempotency_key,
            )
            await self.notifications_repository.set_status(
                notification,
                NotificationStatusEnum.SENT,
                self.now_provider(),
            )
            stats["created"] += 1
        return stats
