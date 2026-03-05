"""Executable worker for periodic package expiration."""

from __future__ import annotations

import asyncio
import logging
import os

from app.core.database import SessionLocal
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.billing.service import BillingService

logger = logging.getLogger(__name__)


async def run_cycle() -> int:
    """Run one package-expiration cycle in one DB transaction."""
    async with SessionLocal() as session:
        service = BillingService(
            repository=BillingRepository(session),
            audit_repository=AuditRepository(session),
        )
        expired_count = await service.expire_packages_system(trigger="worker_expire_packages")
        await session.commit()
        return expired_count


async def main() -> None:
    """Run once or keep polling according to worker mode."""
    logging.basicConfig(level=os.getenv("PACKAGES_EXPIRER_LOG_LEVEL", "INFO"))
    mode = os.getenv("PACKAGES_EXPIRER_MODE", "once").strip().lower()
    poll_seconds = int(os.getenv("PACKAGES_EXPIRER_POLL_SECONDS", "3600"))

    if mode == "once":
        expired_count = await run_cycle()
        logger.info("Packages expirer worker expired_count=%s", expired_count)
        return

    while True:
        try:
            expired_count = await run_cycle()
            logger.info("Packages expirer worker expired_count=%s", expired_count)
        except Exception:
            logger.exception("Packages expirer worker cycle failed")
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
