"""Admin business logic layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.admin.models import AdminAction
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AdminActionCreate,
    AdminKpiOverviewRead,
    AdminOperationsOverviewRead,
    AdminTeacherDetailRead,
    AdminTeacherListItemRead,
)
from app.modules.identity.models import User
from app.shared.exceptions import NotFoundException, UnauthorizedException


class AdminService:
    """Admin domain service."""

    def __init__(self, repository: AdminRepository) -> None:
        self.repository = repository

    async def create_action(self, payload: AdminActionCreate, actor: User) -> AdminAction:
        """Record admin action."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create admin actions")

        return await self.repository.create_action(
            admin_id=actor.id,
            action=payload.action,
            target_type=payload.target_type,
            target_id=payload.target_id,
            payload=payload.payload,
        )

    async def list_actions(
        self,
        actor: User,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminAction], int]:
        """List admin actions."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can list admin actions")
        return await self.repository.list_actions(limit=limit, offset=offset)

    async def get_kpi_overview(self, actor: User) -> AdminKpiOverviewRead:
        """Return aggregated admin KPI snapshot."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view KPI overview")

        snapshot = await self.repository.get_kpi_overview()
        await self.repository.create_action(
            admin_id=actor.id,
            action="admin.kpi.view",
            target_type="kpi_overview",
            target_id=None,
            payload={"generated_at": snapshot["generated_at"].isoformat()},
        )
        return AdminKpiOverviewRead(**snapshot)

    async def get_operations_overview(
        self,
        actor: User,
        *,
        max_retries: int,
    ) -> AdminOperationsOverviewRead:
        """Return operational snapshot for runbook checks."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view operations overview")

        snapshot = await self.repository.get_operations_overview(max_retries=max_retries)
        await self.repository.create_action(
            admin_id=actor.id,
            action="admin.ops.view",
            target_type="operations_overview",
            target_id=None,
            payload={
                "generated_at": snapshot["generated_at"].isoformat(),
                "max_retries": max_retries,
            },
        )
        return AdminOperationsOverviewRead(**snapshot)

    async def list_teachers(
        self,
        actor: User,
        *,
        limit: int,
        offset: int,
        status: TeacherStatusEnum | None,
        verified: bool | None,
        q: str | None,
        tag: str | None,
    ) -> tuple[list[AdminTeacherListItemRead], int]:
        """List teachers with admin filters for scheduling operations."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can list teachers")

        items, total = await self.repository.list_teachers(
            limit=limit,
            offset=offset,
            status=status,
            verified=verified,
            q=q,
            tag=tag,
        )
        return [AdminTeacherListItemRead.model_validate(item) for item in items], total

    async def get_teacher_detail(
        self,
        actor: User,
        *,
        teacher_id: UUID,
    ) -> AdminTeacherDetailRead:
        """Get teacher detail for admin operations."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view teacher detail")

        item = await self.repository.get_teacher_detail(teacher_id=teacher_id)
        if item is None:
            raise NotFoundException("Teacher profile not found")

        return AdminTeacherDetailRead.model_validate(item)

    async def verify_teacher(
        self,
        actor: User,
        *,
        teacher_id: UUID,
    ) -> AdminTeacherDetailRead:
        """Verify teacher profile and return updated detail."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can verify teachers")

        item = await self.repository.verify_teacher(teacher_id=teacher_id, admin_id=actor.id)
        if item is None:
            raise NotFoundException("Teacher profile not found")
        return AdminTeacherDetailRead.model_validate(item)

    async def disable_teacher(
        self,
        actor: User,
        *,
        teacher_id: UUID,
    ) -> AdminTeacherDetailRead:
        """Disable teacher profile and user account."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can disable teachers")

        item = await self.repository.disable_teacher(teacher_id=teacher_id, admin_id=actor.id)
        if item is None:
            raise NotFoundException("Teacher profile not found")
        return AdminTeacherDetailRead.model_validate(item)


async def get_admin_service(session: AsyncSession = Depends(get_db_session)) -> AdminService:
    """Dependency provider for admin service."""
    return AdminService(AdminRepository(session))
