"""Executable worker for 24h lesson reminder notifications."""

from __future__ import annotations

import asyncio
import logging
import os

from app.core.database import SessionLocal
from app.modules.lessons.repository import LessonsRepository
from app.modules.notifications.reminder_worker import LessonReminder24hWorker
from app.modules.notifications.repository import NotificationsRepository

logger = logging.getLogger(__name__)


async def run_cycle() -> dict[str, int]:
    """Run one reminder generation cycle in one DB transaction."""
    async with SessionLocal() as session:
        worker = LessonReminder24hWorker(
            lessons_repository=LessonsRepository(session),
            notifications_repository=NotificationsRepository(session),
            batch_size=int(os.getenv("LESSON_REMINDER_24H_WORKER_BATCH_SIZE", "500")),
            window_hours=int(os.getenv("LESSON_REMINDER_24H_WORKER_WINDOW_HOURS", "24")),
        )
        stats = await worker.run_once()
        await session.commit()
        return stats


async def main() -> None:
    """Run once or keep polling according to worker mode."""
    logging.basicConfig(level=os.getenv("LESSON_REMINDER_24H_WORKER_LOG_LEVEL", "INFO"))
    mode = os.getenv("LESSON_REMINDER_24H_WORKER_MODE", "once").strip().lower()
    poll_seconds = int(os.getenv("LESSON_REMINDER_24H_WORKER_POLL_SECONDS", "3600"))

    if mode == "once":
        stats = await run_cycle()
        logger.info("Lesson reminder 24h worker stats=%s", stats)
        return

    while True:
        try:
            stats = await run_cycle()
            logger.info("Lesson reminder 24h worker stats=%s", stats)
        except Exception:
            logger.exception("Lesson reminder 24h worker cycle failed")
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
