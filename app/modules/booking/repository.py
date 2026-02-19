"""Booking repository layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import RoleEnum
from app.core.enums import BookingStatusEnum
from app.modules.booking.models import Booking


class BookingRepository:
    """DB operations for booking domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_booking_hold(
        self,
        slot_id: UUID,
        student_id: UUID,
        teacher_id: UUID,
        package_id: UUID,
        hold_expires_at: datetime,
    ) -> Booking:
        booking = Booking(
            slot_id=slot_id,
            student_id=student_id,
            teacher_id=teacher_id,
            package_id=package_id,
            status=BookingStatusEnum.HOLD,
            hold_expires_at=hold_expires_at,
        )
        self.session.add(booking)
        await self.session.flush()
        await self.session.refresh(booking, attribute_names=["slot"])
        return booking

    async def get_booking_by_id(self, booking_id: UUID) -> Booking | None:
        stmt = (
            select(Booking)
            .options(selectinload(Booking.slot), selectinload(Booking.package))
            .where(Booking.id == booking_id)
        )
        return await self.session.scalar(stmt)

    async def list_bookings(
        self,
        user_id: UUID,
        role_name: RoleEnum,
        limit: int,
        offset: int,
    ) -> tuple[list[Booking], int]:
        base_stmt: Select[tuple[Booking]] = select(Booking).options(selectinload(Booking.slot))

        if role_name == RoleEnum.STUDENT:
            base_stmt = base_stmt.where(Booking.student_id == user_id)
        elif role_name == RoleEnum.TEACHER:
            base_stmt = base_stmt.where(Booking.teacher_id == user_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(Booking.created_at.desc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def find_expired_holds(self, now: datetime) -> list[Booking]:
        stmt = select(Booking).options(selectinload(Booking.slot)).where(
            Booking.status == BookingStatusEnum.HOLD,
            Booking.hold_expires_at.is_not(None),
            Booking.hold_expires_at <= now,
        )
        return (await self.session.scalars(stmt)).all()

    async def save(self, booking: Booking) -> Booking:
        await self.session.flush()
        return booking
