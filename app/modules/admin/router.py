"""Admin API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.admin.schemas import (
    AdminActionCreate,
    AdminActionRead,
    AdminKpiOverviewRead,
    AdminOperationsOverviewRead,
    AdminTeacherDetailRead,
    AdminTeacherListItemRead,
)
from app.modules.admin.service import AdminService, get_admin_service
from app.modules.identity.service import require_roles
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
