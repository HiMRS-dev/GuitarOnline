"""Scheduling business logic layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.enums import RoleEnum, SlotStatusEnum
from app.modules.audit.repository import AuditRepository
from app.modules.identity.models import User
from app.modules.scheduling.models import AvailabilitySlot
from app.modules.scheduling.repository import SchedulingRepository
from app.modules.scheduling.schemas import SlotCreate
from app.shared.exceptions import BusinessRuleException, NotFoundException, UnauthorizedException
from app.shared.utils import ensure_utc, utc_now

settings = get_settings()


class SchedulingService:
    """Scheduling domain service."""

    def __init__(
        self,
        repository: SchedulingRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.repository = repository
        self.audit_repository = audit_repository

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
        duration_minutes = int((end_at - start_at).total_seconds() // 60)
        if duration_minutes < settings.slot_min_duration_minutes:
            raise BusinessRuleException(
                f"Slot duration must be at least {settings.slot_min_duration_minutes} minutes",
            )

        overlapping_slot = await self.repository.find_overlapping_slot(
            teacher_id=payload.teacher_id,
            start_at=start_at,
            end_at=end_at,
        )
        if overlapping_slot is not None:
            raise BusinessRuleException(
                "Slot overlaps with an existing slot for this teacher",
                details={
                    "overlap_slot_id": str(overlapping_slot.id),
                    "overlap_start_at_utc": overlapping_slot.start_at.isoformat(),
                    "overlap_end_at_utc": overlapping_slot.end_at.isoformat(),
                },
            )

        slot = await self.repository.create_slot(payload.teacher_id, actor.id, start_at, end_at)
        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="admin.slot.create",
            entity_type="availability_slot",
            entity_id=str(slot.id),
            payload={
                "teacher_id": str(slot.teacher_id),
                "start_at_utc": slot.start_at.isoformat(),
                "end_at_utc": slot.end_at.isoformat(),
            },
        )
        return slot

    async def list_open_slots(
        self,
        teacher_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AvailabilitySlot], int]:
        """List open slots with pagination."""
        return await self.repository.list_open_slots(
            teacher_id=teacher_id,
            limit=limit,
            offset=offset,
        )

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


async def get_scheduling_service(
    session: AsyncSession = Depends(get_db_session),
) -> SchedulingService:
    """Dependency provider for scheduling service."""
    return SchedulingService(
        repository=SchedulingRepository(session),
        audit_repository=AuditRepository(session),
    )
