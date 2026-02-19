"""Audit business logic layer."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import RoleEnum
from app.modules.audit.models import AuditLog, OutboxEvent
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogCreate
from app.modules.identity.models import User
from app.shared.exceptions import UnauthorizedException
from app.shared.utils import utc_now


class AuditService:
    """Service for audit logging and outbox management."""

    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    async def create_log(self, payload: AuditLogCreate, actor: User | None) -> AuditLog:
        """Create audit log entry."""
        return await self.repository.create_audit_log(
            actor_id=actor.id if actor else None,
            action=payload.action,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            payload=payload.payload,
        )

    async def list_logs(self, actor: User, limit: int, offset: int) -> tuple[list[AuditLog], int]:
        """List audit logs (admin only)."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view audit logs")
        return await self.repository.list_audit_logs(limit=limit, offset=offset)

    async def list_pending_outbox(self, actor: User, limit: int) -> list[OutboxEvent]:
        """List pending outbox events (admin only)."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view outbox")
        return await self.repository.list_pending_outbox(limit)

    async def mark_processed(self, event: OutboxEvent) -> OutboxEvent:
        """Mark outbox event as processed."""
        return await self.repository.mark_outbox_processed(event, utc_now())


async def get_audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditService:
    """Dependency provider for audit service."""
    return AuditService(AuditRepository(session))
