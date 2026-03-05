"""Scheduling business logic layer."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
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

    async def bulk_create_slots(
        self,
        *,
        teacher_id: UUID,
        date_from_utc: date,
        date_to_utc: date,
        weekdays: list[int],
        start_time_utc: time,
        end_time_utc: time,
        slot_duration_minutes: int,
        actor: User,
    ) -> tuple[list[AvailabilitySlot], list[dict[str, object]]]:
        """Create multiple slots by weekly template with deterministic skip reasons."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create slots")
        if date_to_utc < date_from_utc:
            raise BusinessRuleException("date_from_utc must be less than or equal to date_to_utc")
        if end_time_utc <= start_time_utc:
            raise BusinessRuleException("end_time_utc must be after start_time_utc")
        if slot_duration_minutes < settings.slot_min_duration_minutes:
            raise BusinessRuleException(
                f"slot_duration_minutes must be at least {settings.slot_min_duration_minutes}",
            )

        weekdays_set = set(weekdays)
        duration = timedelta(minutes=slot_duration_minutes)
        day_count = (date_to_utc - date_from_utc).days + 1
        candidates: list[tuple[datetime, datetime]] = []
        for day_offset in range(day_count):
            current_date = date_from_utc + timedelta(days=day_offset)
            if current_date.weekday() not in weekdays_set:
                continue

            cursor = datetime.combine(current_date, start_time_utc, tzinfo=UTC)
            day_end = datetime.combine(current_date, end_time_utc, tzinfo=UTC)
            while cursor + duration <= day_end:
                candidates.append((cursor, cursor + duration))
                cursor += duration

        if len(candidates) > settings.slot_bulk_create_max_slots:
            raise BusinessRuleException(
                f"Bulk create candidates exceed limit ({settings.slot_bulk_create_max_slots})",
            )

        created_slots: list[AvailabilitySlot] = []
        skipped: list[dict[str, object]] = []
        for start_at_utc, end_at_utc in candidates:
            try:
                slot = await self.create_slot(
                    SlotCreate(
                        teacher_id=teacher_id,
                        start_at=start_at_utc,
                        end_at=end_at_utc,
                    ),
                    actor,
                )
                created_slots.append(slot)
            except BusinessRuleException as exc:
                skipped.append(
                    {
                        "start_at_utc": start_at_utc,
                        "end_at_utc": end_at_utc,
                        "reason": exc.message,
                    },
                )

        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="admin.slot.bulk_create",
            entity_type="availability_slot_batch",
            entity_id=str(teacher_id),
            payload={
                "teacher_id": str(teacher_id),
                "date_from_utc": date_from_utc.isoformat(),
                "date_to_utc": date_to_utc.isoformat(),
                "weekdays": sorted(weekdays_set),
                "start_time_utc": start_time_utc.isoformat(),
                "end_time_utc": end_time_utc.isoformat(),
                "slot_duration_minutes": slot_duration_minutes,
                "created_count": len(created_slots),
                "skipped_count": len(skipped),
            },
        )

        return created_slots, skipped

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
