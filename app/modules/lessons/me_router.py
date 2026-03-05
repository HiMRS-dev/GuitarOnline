"""Me lessons API router alias."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.enums import RoleEnum
from app.modules.identity.service import require_roles
from app.modules.lessons.schemas import LessonRead
from app.modules.lessons.service import LessonsService, get_lessons_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/me", tags=["lessons"])


@router.get("/lessons", response_model=Page[LessonRead])
async def list_my_lessons_alias(
    pagination=Depends(get_pagination_params),
    service: LessonsService = Depends(get_lessons_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN, RoleEnum.TEACHER, RoleEnum.STUDENT)),
) -> Page[LessonRead]:
    """Alias for /lessons/my contract stability."""
    items, total = await service.list_lessons(current_user, pagination.limit, pagination.offset)
    serialized = [LessonRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)
