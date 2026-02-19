"""Admin API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.modules.admin.schemas import AdminActionCreate, AdminActionRead
from app.modules.admin.service import AdminService, get_admin_service
from app.modules.identity.service import get_current_user
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/actions", response_model=AdminActionRead, status_code=status.HTTP_201_CREATED)
async def create_admin_action(
    payload: AdminActionCreate,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(get_current_user),
) -> AdminActionRead:
    """Create admin action log."""
    action = await service.create_action(payload, current_user)
    return AdminActionRead.model_validate(action)


@router.get("/actions", response_model=Page[AdminActionRead])
async def list_admin_actions(
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(get_current_user),
) -> Page[AdminActionRead]:
    """List admin action logs."""
    items, total = await service.list_actions(current_user, pagination.limit, pagination.offset)
    serialized = [AdminActionRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)
