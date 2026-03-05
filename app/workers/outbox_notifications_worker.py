"""Executable worker for notifications outbox processing."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from time import monotonic

from app.core.database import SessionLocal
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.notifications.outbox_worker import NotificationsOutboxWorker
from app.modules.notifications.repository import NotificationsRepository

logger = logging.getLogger(__name__)

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MODE = "once"
DEFAULT_POLL_SECONDS = 10
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_BACKOFF_SECONDS = 30
DEFAULT_MAX_BACKOFF_SECONDS = 300


@dataclass(frozen=True, slots=True)
class OutboxNotificationsWorkerConfig:
    """Runtime worker configuration resolved from env vars."""

    log_level: int
    mode: str
    poll_seconds: int
    batch_size: int
    max_retries: int
    base_backoff_seconds: int
    max_backoff_seconds: int


def _read_env_value(primary_name: str, *, legacy_name: str | None, default: str) -> str:
    value = os.getenv(primary_name)
    if value is not None:
        return value

    if legacy_name is None:
        return default

    legacy_value = os.getenv(legacy_name)
    if legacy_value is None:
        return default

    logger.warning(
        "Using legacy env var %s; prefer %s",
        legacy_name,
        primary_name,
    )
    return legacy_value


def _read_env_int(
    primary_name: str,
    *,
    legacy_name: str | None,
    default: int,
    min_value: int = 1,
) -> int:
    raw_value = _read_env_value(
        primary_name,
        legacy_name=legacy_name,
        default=str(default),
    )
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid integer for %s=%r; using default %s",
            primary_name,
            raw_value,
            default,
        )
        return default

    if parsed < min_value:
        logger.warning(
            "Invalid integer for %s=%r (must be >= %s); using default %s",
            primary_name,
            raw_value,
            min_value,
            default,
        )
        return default

    return parsed


def _read_log_level() -> int:
    raw_level = _read_env_value(
        "NOTIFICATIONS_OUTBOX_WORKER_LOG_LEVEL",
        legacy_name="OUTBOX_WORKER_LOG_LEVEL",
        default=DEFAULT_LOG_LEVEL,
    )
    normalized = str(raw_level).strip().upper()
    level_value = getattr(logging, normalized, None)
    if isinstance(level_value, int):
        return level_value

    logger.warning(
        "Invalid log level %r; using default %s",
        raw_level,
        DEFAULT_LOG_LEVEL,
    )
    return getattr(logging, DEFAULT_LOG_LEVEL)


def _read_mode() -> str:
    raw_mode = _read_env_value(
        "NOTIFICATIONS_OUTBOX_WORKER_MODE",
        legacy_name="OUTBOX_WORKER_MODE",
        default=DEFAULT_MODE,
    )
    normalized = str(raw_mode).strip().lower()
    if normalized == "poll":
        return "loop"
    if normalized in {"once", "loop"}:
        return normalized

    logger.warning(
        "Invalid worker mode %r; using default %s",
        raw_mode,
        DEFAULT_MODE,
    )
    return DEFAULT_MODE


def load_worker_config() -> OutboxNotificationsWorkerConfig:
    """Resolve worker runtime settings from env vars."""
    return OutboxNotificationsWorkerConfig(
        log_level=_read_log_level(),
        mode=_read_mode(),
        poll_seconds=_read_env_int(
            "NOTIFICATIONS_OUTBOX_WORKER_POLL_SECONDS",
            legacy_name="OUTBOX_WORKER_POLL_SECONDS",
            default=DEFAULT_POLL_SECONDS,
        ),
        batch_size=_read_env_int(
            "NOTIFICATIONS_OUTBOX_WORKER_BATCH_SIZE",
            legacy_name="OUTBOX_WORKER_BATCH_SIZE",
            default=DEFAULT_BATCH_SIZE,
        ),
        max_retries=_read_env_int(
            "NOTIFICATIONS_OUTBOX_WORKER_MAX_RETRIES",
            legacy_name="OUTBOX_WORKER_MAX_RETRIES",
            default=DEFAULT_MAX_RETRIES,
        ),
        base_backoff_seconds=_read_env_int(
            "NOTIFICATIONS_OUTBOX_WORKER_BASE_BACKOFF_SECONDS",
            legacy_name="OUTBOX_WORKER_BASE_BACKOFF_SECONDS",
            default=DEFAULT_BASE_BACKOFF_SECONDS,
        ),
        max_backoff_seconds=_read_env_int(
            "NOTIFICATIONS_OUTBOX_WORKER_MAX_BACKOFF_SECONDS",
            legacy_name="OUTBOX_WORKER_MAX_BACKOFF_SECONDS",
            default=DEFAULT_MAX_BACKOFF_SECONDS,
        ),
    )


async def run_cycle(config: OutboxNotificationsWorkerConfig | None = None) -> dict[str, int]:
    """Run a single outbox processing cycle in one DB transaction."""
    worker_config = config or load_worker_config()
    async with SessionLocal() as session:
        worker = NotificationsOutboxWorker(
            audit_repository=AuditRepository(session),
            notifications_repository=NotificationsRepository(session),
            billing_repository=BillingRepository(session),
            batch_size=worker_config.batch_size,
            max_retries=worker_config.max_retries,
            base_backoff_seconds=worker_config.base_backoff_seconds,
            max_backoff_seconds=worker_config.max_backoff_seconds,
        )
        stats = await worker.run_once()
        await session.commit()
        return stats


async def main() -> None:
    """Run once or keep polling according to worker mode."""
    config = load_worker_config()
    logging.basicConfig(level=config.log_level)
    logger.info(
        "Outbox notifications worker started mode=%s poll_seconds=%s batch_size=%s "
        "max_retries=%s base_backoff_seconds=%s max_backoff_seconds=%s",
        config.mode,
        config.poll_seconds,
        config.batch_size,
        config.max_retries,
        config.base_backoff_seconds,
        config.max_backoff_seconds,
    )

    if config.mode == "once":
        cycle_started = monotonic()
        stats = await run_cycle(config)
        elapsed_ms = int((monotonic() - cycle_started) * 1000)
        logger.info(
            "Outbox notifications worker cycle succeeded stats=%s elapsed_ms=%s",
            stats,
            elapsed_ms,
        )
        return

    while True:
        cycle_started = monotonic()
        try:
            stats = await run_cycle(config)
            elapsed_ms = int((monotonic() - cycle_started) * 1000)
            logger.info(
                "Outbox notifications worker cycle succeeded stats=%s elapsed_ms=%s",
                stats,
                elapsed_ms,
            )
        except Exception:
            elapsed_ms = int((monotonic() - cycle_started) * 1000)
            logger.exception(
                "Outbox notifications worker cycle failed elapsed_ms=%s",
                elapsed_ms,
            )
        await asyncio.sleep(config.poll_seconds)


if __name__ == "__main__":
    asyncio.run(main())
