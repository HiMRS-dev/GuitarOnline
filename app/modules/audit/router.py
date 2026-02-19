"""Audit API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.audit.schemas import AuditLogCreate, AuditLogRead, OutboxEventRead
from app.modules.audit.service import AuditService, get_audit_service
from app.modules.identity.service import get_current_user
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/audit", tags=["audit"])


@router.post("/logs", response_model=AuditLogRead)
async def create_log(
    payload: AuditLogCreate,
    service: AuditService = Depends(get_audit_service),
    current_user=Depends(get_current_user),
) -> AuditLogRead:
    """Create audit log entry."""
    log = await service.create_log(payload, current_user)
    return AuditLogRead.model_validate(log)


@router.get("/logs", response_model=Page[AuditLogRead])
async def list_logs(
    pagination=Depends(get_pagination_params),
    service: AuditService = Depends(get_audit_service),
    current_user=Depends(get_current_user),
) -> Page[AuditLogRead]:
    """List audit logs."""
    items, total = await service.list_logs(current_user, pagination.limit, pagination.offset)
    serialized = [AuditLogRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)


@router.get("/outbox/pending", response_model=list[OutboxEventRead])
async def list_pending_outbox(
    limit: int = 100,
    service: AuditService = Depends(get_audit_service),
    current_user=Depends(get_current_user),
) -> list[OutboxEventRead]:
    """List pending outbox events."""
    items = await service.list_pending_outbox(current_user, limit=limit)
    return [OutboxEventRead.model_validate(item) for item in items]
