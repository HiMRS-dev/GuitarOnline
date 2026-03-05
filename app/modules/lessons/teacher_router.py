"""Teacher lessons API router."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.enums import RoleEnum
from app.modules.identity.service import require_roles
from app.modules.lessons.schemas import LessonRead, TeacherLessonReportRequest
from app.modules.lessons.service import LessonsService, get_lessons_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/teacher", tags=["lessons"])


@router.get("/lessons", response_model=Page[LessonRead])
async def list_teacher_lessons(
    from_utc: datetime | None = Query(default=None),
    to_utc: datetime | None = Query(default=None),
    pagination=Depends(get_pagination_params),
    service: LessonsService = Depends(get_lessons_service),
    current_user=Depends(require_roles(RoleEnum.TEACHER)),
) -> Page[LessonRead]:
    """List teacher-owned lessons with optional UTC range filters."""
    items, total = await service.list_teacher_lessons(
        current_user,
        from_utc=from_utc,
        to_utc=to_utc,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    serialized = [LessonRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)


@router.post("/lessons/{lesson_id}/report", response_model=LessonRead)
async def report_teacher_lesson(
    lesson_id: UUID,
    payload: TeacherLessonReportRequest,
    service: LessonsService = Depends(get_lessons_service),
    current_user=Depends(require_roles(RoleEnum.TEACHER)),
) -> LessonRead:
    """Save teacher report payload for own lesson."""
    lesson = await service.report_lesson(lesson_id, payload, current_user)
    return LessonRead.model_validate(lesson)
