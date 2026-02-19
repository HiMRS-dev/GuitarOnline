"""Lessons business logic layer."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import RoleEnum
from app.modules.identity.models import User
from app.modules.lessons.models import Lesson
from app.modules.lessons.repository import LessonsRepository
from app.modules.lessons.schemas import LessonCreate, LessonUpdate
from app.shared.exceptions import ConflictException, NotFoundException, UnauthorizedException
from app.shared.utils import ensure_utc


class LessonsService:
    """Lessons domain service."""

    def __init__(self, repository: LessonsRepository) -> None:
        self.repository = repository

    async def create_lesson(self, payload: LessonCreate, actor: User) -> Lesson:
        """Create lesson entity from booking data."""
        if actor.role.name not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
            raise UnauthorizedException("Only admin or teacher can create lessons")

        existing = await self.repository.get_lesson_by_booking_id(payload.booking_id)
        if existing is not None:
            raise ConflictException("Lesson already exists for booking")

        start_at = ensure_utc(payload.scheduled_start_at)
        end_at = ensure_utc(payload.scheduled_end_at)
        if end_at <= start_at:
            from app.shared.exceptions import BusinessRuleException

            raise BusinessRuleException("Lesson end must be greater than start")

        return await self.repository.create_lesson(
            booking_id=payload.booking_id,
            student_id=payload.student_id,
            teacher_id=payload.teacher_id,
            scheduled_start_at=start_at,
            scheduled_end_at=end_at,
            topic=payload.topic,
            notes=payload.notes,
        )

    async def update_lesson(self, lesson_id, payload: LessonUpdate, actor: User) -> Lesson:
        """Update lesson details or status."""
        lesson = await self.repository.get_lesson_by_id(lesson_id)
        if lesson is None:
            raise NotFoundException("Lesson not found")

        if actor.role.name not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
            raise UnauthorizedException("Only admin or teacher can update lessons")

        if actor.role.name == RoleEnum.TEACHER and lesson.teacher_id != actor.id:
            raise UnauthorizedException("Teacher can update only own lessons")

        return await self.repository.update_lesson(lesson, **payload.model_dump(exclude_none=True))

    async def list_lessons(self, actor: User, limit: int, offset: int) -> tuple[list[Lesson], int]:
        """List lessons according to actor role."""
        return await self.repository.list_lessons_for_user(actor.id, actor.role.name, limit, offset)


async def get_lessons_service(session: AsyncSession = Depends(get_db_session)) -> LessonsService:
    """Dependency provider for lessons service."""
    return LessonsService(LessonsRepository(session))
