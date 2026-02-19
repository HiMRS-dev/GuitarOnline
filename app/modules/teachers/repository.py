"""Teachers repository layer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.teachers.models import TeacherProfile


class TeachersRepository:
    """DB operations for teachers domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_profile(
        self,
        user_id: UUID,
        display_name: str,
        bio: str,
        experience_years: int,
    ) -> TeacherProfile:
        profile = TeacherProfile(
            user_id=user_id,
            display_name=display_name,
            bio=bio,
            experience_years=experience_years,
        )
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_profile_by_id(self, profile_id: UUID) -> TeacherProfile | None:
        stmt = select(TeacherProfile).where(TeacherProfile.id == profile_id)
        return await self.session.scalar(stmt)

    async def get_profile_by_user_id(self, user_id: UUID) -> TeacherProfile | None:
        stmt = select(TeacherProfile).where(TeacherProfile.user_id == user_id)
        return await self.session.scalar(stmt)

    async def list_profiles(self, limit: int, offset: int) -> tuple[list[TeacherProfile], int]:
        base_stmt: Select[tuple[TeacherProfile]] = select(TeacherProfile)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(TeacherProfile.created_at.desc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def update_profile(self, profile: TeacherProfile, **changes) -> TeacherProfile:
        for key, value in changes.items():
            if value is not None:
                setattr(profile, key, value)
        await self.session.flush()
        return profile
