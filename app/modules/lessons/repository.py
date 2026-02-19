"""Lessons repository layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RoleEnum
from app.modules.lessons.models import Lesson


class LessonsRepository:
    """DB operations for lessons domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_lesson(
        self,
        booking_id: UUID,
        student_id: UUID,
        teacher_id: UUID,
        scheduled_start_at,
        scheduled_end_at,
        topic,
        notes,
    ) -> Lesson:
        lesson = Lesson(
            booking_id=booking_id,
            student_id=student_id,
            teacher_id=teacher_id,
            scheduled_start_at=scheduled_start_at,
            scheduled_end_at=scheduled_end_at,
            topic=topic,
            notes=notes,
        )
        self.session.add(lesson)
        await self.session.flush()
        return lesson

    async def get_lesson_by_id(self, lesson_id: UUID) -> Lesson | None:
        stmt = select(Lesson).where(Lesson.id == lesson_id)
        return await self.session.scalar(stmt)

    async def get_lesson_by_booking_id(self, booking_id: UUID) -> Lesson | None:
        stmt = select(Lesson).where(Lesson.booking_id == booking_id)
        return await self.session.scalar(stmt)

    async def list_lessons_for_user(
        self,
        user_id: UUID,
        role_name: RoleEnum,
        limit: int,
        offset: int,
    ) -> tuple[list[Lesson], int]:
        base_stmt: Select[tuple[Lesson]] = select(Lesson)

        if role_name == RoleEnum.STUDENT:
            base_stmt = base_stmt.where(Lesson.student_id == user_id)
        elif role_name == RoleEnum.TEACHER:
            base_stmt = base_stmt.where(Lesson.teacher_id == user_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(Lesson.scheduled_start_at.asc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def update_lesson(self, lesson: Lesson, **changes) -> Lesson:
        for key, value in changes.items():
            if value is not None:
                setattr(lesson, key, value)
        await self.session.flush()
        return lesson
