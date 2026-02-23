"""Admin business logic layer."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import RoleEnum
from app.modules.admin.models import AdminAction
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AdminActionCreate,
    AdminKpiOverviewRead,
    AdminOperationsOverviewRead,
)
from app.modules.identity.models import User
from app.shared.exceptions import UnauthorizedException


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


async def get_admin_service(session: AsyncSession = Depends(get_db_session)) -> AdminService:
    """Dependency provider for admin service."""
    return AdminService(AdminRepository(session))
