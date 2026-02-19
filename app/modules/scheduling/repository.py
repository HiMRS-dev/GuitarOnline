"""Scheduling repository layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SlotStatusEnum
from app.modules.scheduling.models import AvailabilitySlot


class SchedulingRepository:
    """DB access for scheduling domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_slot(
        self,
        teacher_id: UUID,
        created_by_admin_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> AvailabilitySlot:
        slot = AvailabilitySlot(
            teacher_id=teacher_id,
            created_by_admin_id=created_by_admin_id,
            start_at=start_at,
            end_at=end_at,
            status=SlotStatusEnum.OPEN,
        )
        self.session.add(slot)
        await self.session.flush()
        return slot

    async def get_slot_by_id(self, slot_id: UUID) -> AvailabilitySlot | None:
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
        return await self.session.scalar(stmt)

    async def list_open_slots(self, teacher_id: UUID | None, limit: int, offset: int) -> tuple[list[AvailabilitySlot], int]:
        base_stmt: Select[tuple[AvailabilitySlot]] = select(AvailabilitySlot).where(
            AvailabilitySlot.status == SlotStatusEnum.OPEN,
        )
        if teacher_id is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.teacher_id == teacher_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(AvailabilitySlot.start_at.asc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def set_slot_status(self, slot: AvailabilitySlot, status: SlotStatusEnum) -> AvailabilitySlot:
        slot.status = status
        await self.session.flush()
        return slot
