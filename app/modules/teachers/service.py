"""Teachers business logic layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.identity.models import User
from app.modules.teachers.models import TeacherProfile
from app.modules.teachers.repository import TeachersRepository
from app.modules.teachers.schemas import TeacherProfileCreate, TeacherProfileUpdate
from app.shared.exceptions import ConflictException, NotFoundException, UnauthorizedException


class TeachersService:
    """Teachers domain service."""

    def __init__(
        self,
        repository: TeachersRepository,
    ) -> None:
        self.repository = repository

    async def create_profile(self, payload: TeacherProfileCreate, actor: User) -> TeacherProfile:
        """Create teacher profile."""
        is_admin = actor.role.name == RoleEnum.ADMIN
        is_teacher_owner = (
            actor.role.name == RoleEnum.TEACHER
            and str(actor.id) == str(payload.user_id)
        )
        if not (is_admin or is_teacher_owner):
            raise UnauthorizedException("Only admin or teacher-owner can create profile")

        existing = await self.repository.get_profile_by_user_id(payload.user_id)
        if existing is not None:
            raise ConflictException("Teacher profile already exists for user")

        return await self.repository.create_profile(
            user_id=payload.user_id,
            display_name=payload.display_name,
            bio=payload.bio,
            experience_years=payload.experience_years,
            status=TeacherStatusEnum.ACTIVE,
        )

    async def update_profile(
        self,
        profile_id: UUID,
        payload: TeacherProfileUpdate,
        actor: User,
    ) -> TeacherProfile:
        """Update teacher profile."""
        profile = await self.repository.get_profile_by_id(profile_id)
        if profile is None:
            raise NotFoundException("Teacher profile not found")

        is_admin = actor.role.name == RoleEnum.ADMIN
        is_teacher_owner = (
            actor.role.name == RoleEnum.TEACHER
            and str(actor.id) == str(profile.user_id)
        )
        if not (is_admin or is_teacher_owner):
            raise UnauthorizedException("Only admin or teacher-owner can update profile")

        changes = payload.model_dump(exclude_none=True)
        return await self.repository.update_profile(profile, **changes)

    async def list_profiles(self, limit: int, offset: int) -> tuple[list[TeacherProfile], int]:
        """List teacher profiles."""
        return await self.repository.list_profiles(limit=limit, offset=offset)


async def get_teachers_service(session: AsyncSession = Depends(get_db_session)) -> TeachersService:
    """Dependency provider for teachers service."""
    return TeachersService(repository=TeachersRepository(session))
