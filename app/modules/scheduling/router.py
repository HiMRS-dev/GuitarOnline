"""Scheduling API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.modules.identity.service import get_current_user
from app.modules.scheduling.schemas import SlotCreate, SlotRead
from app.modules.scheduling.service import SchedulingService, get_scheduling_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


@router.post("/slots", response_model=SlotRead, status_code=status.HTTP_201_CREATED)
async def create_slot(
    payload: SlotCreate,
    service: SchedulingService = Depends(get_scheduling_service),
    current_user=Depends(get_current_user),
) -> SlotRead:
    """Create availability slot."""
    slot = await service.create_slot(payload, current_user)
    return SlotRead.model_validate(slot)


@router.get("/slots/open", response_model=Page[SlotRead])
async def list_open_slots(
    teacher_id: UUID | None = Query(default=None),
    pagination=Depends(get_pagination_params),
    service: SchedulingService = Depends(get_scheduling_service),
) -> Page[SlotRead]:
    """List currently open slots."""
    items, total = await service.list_open_slots(teacher_id, pagination.limit, pagination.offset)
    serialized = [SlotRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)
