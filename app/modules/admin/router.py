"""Admin API router."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.admin.schemas import (
    AdminActionCreate,
    AdminActionRead,
    AdminKpiOverviewRead,
    AdminOperationsOverviewRead,
    AdminSlotCreateRead,
    AdminSlotCreateRequest,
    AdminSlotListItemRead,
    AdminTeacherDetailRead,
    AdminTeacherListItemRead,
)
from app.modules.admin.service import AdminService, get_admin_service
from app.modules.identity.service import require_roles
from app.modules.scheduling.schemas import SlotCreate
from app.modules.scheduling.service import SchedulingService, get_scheduling_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/actions", response_model=AdminActionRead, status_code=status.HTTP_201_CREATED)
async def create_admin_action(
    payload: AdminActionCreate,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminActionRead:
    """Create admin action log."""
    action = await service.create_action(payload, current_user)
    return AdminActionRead.model_validate(action)


@router.get("/actions", response_model=Page[AdminActionRead])
async def list_admin_actions(
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminActionRead]:
    """List admin action logs."""
    items, total = await service.list_actions(current_user, pagination.limit, pagination.offset)
    serialized = [AdminActionRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)


@router.get("/teachers", response_model=Page[AdminTeacherListItemRead])
async def list_admin_teachers(
    status_filter: TeacherStatusEnum | None = Query(default=None, alias="status"),
    verified: bool | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=255),
    tag: str | None = Query(default=None, min_length=1, max_length=64),
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminTeacherListItemRead]:
    """List teachers for admin filters by status/verification/query/tag."""
    items, total = await service.list_teachers(
        current_user,
        limit=pagination.limit,
        offset=pagination.offset,
        status=status_filter,
        verified=verified,
        q=q,
        tag=tag,
    )
    return build_page(items, total, pagination)


@router.get("/teachers/{teacher_id}", response_model=AdminTeacherDetailRead)
async def get_admin_teacher_detail(
    teacher_id: UUID,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminTeacherDetailRead:
    """Get teacher detail for admin views."""
    return await service.get_teacher_detail(current_user, teacher_id=teacher_id)


@router.post("/teachers/{teacher_id}/verify", response_model=AdminTeacherDetailRead)
async def verify_admin_teacher(
    teacher_id: UUID,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminTeacherDetailRead:
    """Verify teacher profile from admin panel."""
    return await service.verify_teacher(current_user, teacher_id=teacher_id)


@router.post("/teachers/{teacher_id}/disable", response_model=AdminTeacherDetailRead)
async def disable_admin_teacher(
    teacher_id: UUID,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminTeacherDetailRead:
    """Disable teacher profile from admin panel."""
    return await service.disable_teacher(current_user, teacher_id=teacher_id)


@router.post("/slots", response_model=AdminSlotCreateRead, status_code=status.HTTP_201_CREATED)
async def create_admin_slot(
    payload: AdminSlotCreateRequest,
    service: SchedulingService = Depends(get_scheduling_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminSlotCreateRead:
    """Create availability slot with strict admin validation."""
    slot = await service.create_slot(
        SlotCreate(
            teacher_id=payload.teacher_id,
            start_at=payload.start_at_utc,
            end_at=payload.end_at_utc,
        ),
        current_user,
    )
    return AdminSlotCreateRead(
        slot_id=slot.id,
        teacher_id=slot.teacher_id,
        created_by_admin_id=slot.created_by_admin_id,
        start_at_utc=slot.start_at,
        end_at_utc=slot.end_at,
        slot_status=slot.status,
        created_at_utc=slot.created_at,
        updated_at_utc=slot.updated_at,
    )


@router.get("/slots", response_model=Page[AdminSlotListItemRead])
async def list_admin_slots(
    teacher_id: UUID | None = Query(default=None),
    from_utc: datetime | None = Query(default=None),
    to_utc: datetime | None = Query(default=None),
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminSlotListItemRead]:
    """List slots for admin calendar views with aggregated booking status."""
    items, total = await service.list_slots(
        current_user,
        teacher_id=teacher_id,
        from_utc=from_utc,
        to_utc=to_utc,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(items, total, pagination)


@router.get("/kpi/overview", response_model=AdminKpiOverviewRead)
async def get_admin_kpi_overview(
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminKpiOverviewRead:
    """Get admin KPI overview snapshot."""
    return await service.get_kpi_overview(current_user)


@router.get("/ops/overview", response_model=AdminOperationsOverviewRead)
async def get_admin_operations_overview(
    max_retries: int = Query(default=5, ge=1, le=100),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminOperationsOverviewRead:
    """Get operational overview snapshot."""
    return await service.get_operations_overview(current_user, max_retries=max_retries)
