"""Audit repository layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OutboxStatusEnum
from app.modules.audit.models import AuditLog, OutboxEvent


class AuditRepository:
    """DB operations for audit and outbox."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_audit_log(
        self,
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict,
    ) -> AuditLog:
        log = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_audit_logs(self, limit: int, offset: int) -> tuple[list[AuditLog], int]:
        base_stmt: Select[tuple[AuditLog]] = select(AuditLog)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def create_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict,
    ) -> OutboxEvent:
        event = OutboxEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            status=OutboxStatusEnum.PENDING,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_pending_outbox(self, limit: int) -> list[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.status == OutboxStatusEnum.PENDING)
            .order_by(OutboxEvent.occurred_at.asc())
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all()

    async def list_failed_outbox(self, limit: int, max_retries: int) -> list[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatusEnum.FAILED,
                OutboxEvent.retries < max_retries,
            )
            .order_by(OutboxEvent.updated_at.asc())
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all()

    async def mark_outbox_pending(self, event: OutboxEvent) -> OutboxEvent:
        event.status = OutboxStatusEnum.PENDING
        event.error_message = None
        event.processed_at = None
        await self.session.flush()
        return event

    async def mark_outbox_processed(
        self,
        event: OutboxEvent,
        processed_at: datetime,
    ) -> OutboxEvent:
        event.status = OutboxStatusEnum.PROCESSED
        event.processed_at = processed_at
        event.error_message = None
        await self.session.flush()
        return event

    async def mark_outbox_failed(self, event: OutboxEvent, error_message: str) -> OutboxEvent:
        event.status = OutboxStatusEnum.FAILED
        event.retries += 1
        event.error_message = error_message
        event.processed_at = None
        await self.session.flush()
        return event

    async def count_outbox_by_status(self) -> dict[OutboxStatusEnum, int]:
        stmt = select(OutboxEvent.status, func.count()).group_by(OutboxEvent.status)
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def count_retryable_failed_outbox(self, max_retries: int) -> int:
        stmt = select(func.count()).where(
            OutboxEvent.status == OutboxStatusEnum.FAILED,
            OutboxEvent.retries < max_retries,
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def count_dead_letter_outbox(self, max_retries: int) -> int:
        stmt = select(func.count()).where(
            OutboxEvent.status == OutboxStatusEnum.FAILED,
            OutboxEvent.retries >= max_retries,
        )
        return int((await self.session.scalar(stmt)) or 0)
