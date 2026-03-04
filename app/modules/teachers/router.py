"""Teachers API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.enums import RoleEnum
from app.modules.identity.service import require_roles
from app.modules.teachers.schemas import (
    TeacherProfileCreate,
    TeacherProfileRead,
    TeacherProfileUpdate,
)
from app.modules.teachers.service import TeachersService, get_teachers_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/teachers", tags=["teachers"])


@router.post("/profiles", response_model=TeacherProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: TeacherProfileCreate,
    service: TeachersService = Depends(get_teachers_service),
    current_user=Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN)),
) -> TeacherProfileRead:
    """Create teacher profile."""
    profile = await service.create_profile(payload, current_user)
    return TeacherProfileRead.model_validate(profile)


@router.patch("/profiles/{profile_id}", response_model=TeacherProfileRead)
async def update_profile(
    profile_id: UUID,
    payload: TeacherProfileUpdate,
    service: TeachersService = Depends(get_teachers_service),
    current_user=Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN)),
) -> TeacherProfileRead:
    """Update teacher profile."""
    profile = await service.update_profile(profile_id, payload, current_user)
    return TeacherProfileRead.model_validate(profile)


@router.get("/profiles", response_model=Page[TeacherProfileRead])
async def list_profiles(
    pagination=Depends(get_pagination_params),
    service: TeachersService = Depends(get_teachers_service),
    _=Depends(require_roles(RoleEnum.TEACHER, RoleEnum.ADMIN)),
) -> Page[TeacherProfileRead]:
    """List teacher profiles."""
    items, total = await service.list_profiles(pagination.limit, pagination.offset)
    serialized = [TeacherProfileRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)
