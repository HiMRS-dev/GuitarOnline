"""Lessons API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.identity.service import get_current_user
from app.modules.lessons.schemas import LessonCreate, LessonRead, LessonUpdate
from app.modules.lessons.service import LessonsService, get_lessons_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post("", response_model=LessonRead, status_code=status.HTTP_201_CREATED)
async def create_lesson(
    payload: LessonCreate,
    service: LessonsService = Depends(get_lessons_service),
    current_user=Depends(get_current_user),
) -> LessonRead:
    """Create lesson."""
    lesson = await service.create_lesson(payload, current_user)
    return LessonRead.model_validate(lesson)


@router.patch("/{lesson_id}", response_model=LessonRead)
async def update_lesson(
    lesson_id: UUID,
    payload: LessonUpdate,
    service: LessonsService = Depends(get_lessons_service),
    current_user=Depends(get_current_user),
) -> LessonRead:
    """Update lesson."""
    lesson = await service.update_lesson(lesson_id, payload, current_user)
    return LessonRead.model_validate(lesson)


@router.get("/my", response_model=Page[LessonRead])
async def list_my_lessons(
    pagination=Depends(get_pagination_params),
    service: LessonsService = Depends(get_lessons_service),
    current_user=Depends(get_current_user),
) -> Page[LessonRead]:
    """List lessons for current user."""
    items, total = await service.list_lessons(current_user, pagination.limit, pagination.offset)
    serialized = [LessonRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)
