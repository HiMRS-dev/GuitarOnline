"""Scheduling business logic layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import RoleEnum, SlotStatusEnum
from app.modules.identity.models import User
from app.modules.scheduling.models import AvailabilitySlot
from app.modules.scheduling.repository import SchedulingRepository
from app.modules.scheduling.schemas import SlotCreate
from app.shared.exceptions import BusinessRuleException, NotFoundException, UnauthorizedException
from app.shared.utils import ensure_utc, utc_now


class SchedulingService:
    """Scheduling domain service."""

    def __init__(self, repository: SchedulingRepository) -> None:
        self.repository = repository

    async def create_slot(self, payload: SlotCreate, actor: User) -> AvailabilitySlot:
        """Create teacher availability slot (admin only)."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create slots")

        start_at = ensure_utc(payload.start_at)
        end_at = ensure_utc(payload.end_at)

        if end_at <= start_at:
            raise BusinessRuleException("Slot end_at must be after start_at")
        if start_at <= utc_now():
            raise BusinessRuleException("Slot start_at must be in the future")

        return await self.repository.create_slot(payload.teacher_id, actor.id, start_at, end_at)

    async def list_open_slots(
        self,
        teacher_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AvailabilitySlot], int]:
        """List open slots with pagination."""
        return await self.repository.list_open_slots(teacher_id=teacher_id, limit=limit, offset=offset)

    async def get_slot_for_booking(self, slot_id: UUID) -> AvailabilitySlot:
        """Return slot that can be used for booking hold."""
        slot = await self.repository.get_slot_by_id(slot_id)
        if slot is None:
            raise NotFoundException("Slot not found")
        if slot.status != SlotStatusEnum.OPEN:
            raise BusinessRuleException("Slot is not available for booking")
        return slot

    async def mark_slot_hold(self, slot: AvailabilitySlot) -> None:
        """Move slot to HOLD state."""
        await self.repository.set_slot_status(slot, SlotStatusEnum.HOLD)

    async def mark_slot_booked(self, slot: AvailabilitySlot) -> None:
        """Move slot to BOOKED state."""
        await self.repository.set_slot_status(slot, SlotStatusEnum.BOOKED)

    async def release_slot(self, slot: AvailabilitySlot) -> None:
        """Return slot to OPEN state."""
        await self.repository.set_slot_status(slot, SlotStatusEnum.OPEN)


async def get_scheduling_service(session: AsyncSession = Depends(get_db_session)) -> SchedulingService:
    """Dependency provider for scheduling service."""
    return SchedulingService(SchedulingRepository(session))
