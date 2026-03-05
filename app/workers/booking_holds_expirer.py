"""Executable worker for periodic booking HOLD expiration."""

from __future__ import annotations

import asyncio
import logging
import os

from app.core.database import SessionLocal
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.booking.repository import BookingRepository
from app.modules.booking.service import BookingService
from app.modules.lessons.repository import LessonsRepository
from app.modules.scheduling.repository import SchedulingRepository

logger = logging.getLogger(__name__)


async def run_cycle() -> int:
    """Run a single HOLD-expiration cycle in one DB transaction."""
    async with SessionLocal() as session:
        service = BookingService(
            booking_repository=BookingRepository(session),
            scheduling_repository=SchedulingRepository(session),
            billing_repository=BillingRepository(session),
            lessons_repository=LessonsRepository(session),
            audit_repository=AuditRepository(session),
        )
        expired_count = await service.expire_holds_system()
        await session.commit()
        return expired_count


async def main() -> None:
    """Run once or keep polling according to worker mode."""
    logging.basicConfig(level=os.getenv("BOOKING_HOLDS_EXPIRER_LOG_LEVEL", "INFO"))
    mode = os.getenv("BOOKING_HOLDS_EXPIRER_MODE", "once").strip().lower()
    poll_seconds = int(os.getenv("BOOKING_HOLDS_EXPIRER_POLL_SECONDS", "30"))

    if mode == "once":
        expired_count = await run_cycle()
        logger.info("Booking holds expirer worker expired_count=%s", expired_count)
        return

    while True:
        try:
            expired_count = await run_cycle()
            logger.info("Booking holds expirer worker expired_count=%s", expired_count)
        except Exception:
            logger.exception("Booking holds expirer worker cycle failed")
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
