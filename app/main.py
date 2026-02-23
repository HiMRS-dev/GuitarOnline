"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal, close_engine
from app.modules.admin.router import router as admin_router
from app.modules.audit.router import router as audit_router
from app.modules.billing.router import router as billing_router
from app.modules.booking.router import router as booking_router
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.router import router as identity_router
from app.modules.identity.service import IdentityService
from app.modules.lessons.router import router as lessons_router
from app.modules.notifications.router import router as notifications_router
from app.modules.scheduling.router import router as scheduling_router
from app.modules.teachers.router import router as teachers_router
from app.shared.exceptions import register_exception_handlers
from app.shared.utils import utc_now

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup and shutdown hooks."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting %s", settings.app_name)

    async with SessionLocal() as session:
        try:
            service = IdentityService(IdentityRepository(session))
            await service.ensure_default_roles()
            await session.commit()
            logger.info("Default roles ensured")
        except Exception:
            await session.rollback()
            logger.exception("Failed during startup initialization")
            raise

    yield

    logger.info("Shutting down %s", settings.app_name)
    await close_engine()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(identity_router, prefix=settings.api_prefix)
app.include_router(teachers_router, prefix=settings.api_prefix)
app.include_router(scheduling_router, prefix=settings.api_prefix)
app.include_router(booking_router, prefix=settings.api_prefix)
app.include_router(billing_router, prefix=settings.api_prefix)
app.include_router(lessons_router, prefix=settings.api_prefix)
app.include_router(notifications_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(audit_router, prefix=settings.api_prefix)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}


async def _is_database_ready() -> bool:
    """Return True if DB accepts basic queries."""
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database readiness check failed")
        return False


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe endpoint with DB dependency check."""
    if not await _is_database_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready",
        )
    return {
        "status": "ready",
        "database": "ok",
        "timestamp": utc_now().isoformat(),
    }
