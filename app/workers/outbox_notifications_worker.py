"""Executable worker for notifications outbox processing."""

from __future__ import annotations

import asyncio
import logging
import os

from app.core.database import SessionLocal
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.notifications.outbox_worker import NotificationsOutboxWorker
from app.modules.notifications.repository import NotificationsRepository

logger = logging.getLogger(__name__)


async def run_cycle() -> dict[str, int]:
    """Run a single outbox processing cycle in one DB transaction."""
    async with SessionLocal() as session:
        worker = NotificationsOutboxWorker(
            audit_repository=AuditRepository(session),
            notifications_repository=NotificationsRepository(session),
            billing_repository=BillingRepository(session),
            batch_size=int(os.getenv("OUTBOX_WORKER_BATCH_SIZE", "100")),
            max_retries=int(os.getenv("OUTBOX_WORKER_MAX_RETRIES", "5")),
            base_backoff_seconds=int(os.getenv("OUTBOX_WORKER_BASE_BACKOFF_SECONDS", "30")),
            max_backoff_seconds=int(os.getenv("OUTBOX_WORKER_MAX_BACKOFF_SECONDS", "300")),
        )
        stats = await worker.run_once()
        await session.commit()
        return stats


async def main() -> None:
    """Run once or keep polling according to worker mode."""
    logging.basicConfig(level=os.getenv("OUTBOX_WORKER_LOG_LEVEL", "INFO"))
    mode = os.getenv("OUTBOX_WORKER_MODE", "once").strip().lower()
    poll_seconds = int(os.getenv("OUTBOX_WORKER_POLL_SECONDS", "10"))

    if mode == "once":
        stats = await run_cycle()
        logger.info("Outbox notifications worker stats: %s", stats)
        return

    while True:
        try:
            stats = await run_cycle()
            logger.info("Outbox notifications worker stats: %s", stats)
        except Exception:
            logger.exception("Outbox notifications worker cycle failed")
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
