"""Booking repository layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import BookingStatusEnum, PackageStatusEnum, RoleEnum
from app.modules.billing.models import LessonPackage
from app.modules.booking.models import Booking
from app.modules.identity.models import User


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

    async def get_booking_by_id_for_update(self, booking_id: UUID) -> Booking | None:
        """Load booking row with write lock for status transitions."""
        stmt = (
            select(Booking)
            .options(selectinload(Booking.slot), selectinload(Booking.package))
            .where(Booking.id == booking_id)
            .with_for_update()
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

    async def list_teacher_students_with_packages(
        self,
        teacher_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        """List active teacher students with package balance snapshots."""
        active_booking_statuses = (BookingStatusEnum.HOLD, BookingStatusEnum.CONFIRMED)
        active_students_base_stmt = (
            select(
                Booking.student_id.label("student_id"),
                func.max(Booking.created_at).label("last_booking_at"),
                func.count(Booking.id).label("active_bookings_count"),
            )
            .where(
                Booking.teacher_id == teacher_id,
                Booking.status.in_(active_booking_statuses),
            )
            .group_by(Booking.student_id)
        )
        active_students_subquery = active_students_base_stmt.subquery()

        count_stmt = select(func.count()).select_from(active_students_subquery)
        total = int((await self.session.scalar(count_stmt)) or 0)

        students_stmt = (
            select(
                active_students_subquery.c.student_id,
                active_students_subquery.c.last_booking_at,
                active_students_subquery.c.active_bookings_count,
                User.email.label("student_email"),
                User.full_name.label("student_full_name"),
            )
            .join(User, User.id == active_students_subquery.c.student_id)
            .order_by(active_students_subquery.c.last_booking_at.desc())
            .limit(limit)
            .offset(offset)
        )
        student_rows = (await self.session.execute(students_stmt)).mappings().all()

        student_ids = [row["student_id"] for row in student_rows]
        if not student_ids:
            return [], total

        packages_stmt = (
            select(
                LessonPackage.student_id.label("student_id"),
                LessonPackage.id.label("package_id"),
                LessonPackage.status.label("status"),
                LessonPackage.lessons_total.label("lessons_total"),
                LessonPackage.lessons_left.label("lessons_left"),
                LessonPackage.lessons_reserved.label("lessons_reserved"),
                LessonPackage.expires_at.label("expires_at"),
            )
            .where(
                LessonPackage.student_id.in_(student_ids),
                LessonPackage.status == PackageStatusEnum.ACTIVE,
            )
            .order_by(LessonPackage.expires_at.asc(), LessonPackage.created_at.desc())
        )
        package_rows = (await self.session.execute(packages_stmt)).mappings().all()

        packages_by_student_id: dict[UUID, list[dict]] = {}
        for package_row in package_rows:
            student_id = package_row["student_id"]
            lessons_left = int(package_row["lessons_left"])
            lessons_reserved = int(package_row["lessons_reserved"])
            package_snapshot = {
                "package_id": package_row["package_id"],
                "status": package_row["status"],
                "lessons_total": int(package_row["lessons_total"]),
                "lessons_left": lessons_left,
                "lessons_reserved": lessons_reserved,
                "lessons_available": max(lessons_left - lessons_reserved, 0),
                "expires_at": package_row["expires_at"],
            }
            packages_by_student_id.setdefault(student_id, []).append(package_snapshot)

        items: list[dict] = []
        for row in student_rows:
            student_id = row["student_id"]
            full_name = str(row["student_full_name"] or "").strip()
            items.append(
                {
                    "student_id": student_id,
                    "student_email": row["student_email"],
                    "student_full_name": full_name or row["student_email"],
                    "active_bookings_count": int(row["active_bookings_count"]),
                    "last_booking_at": row["last_booking_at"],
                    "packages": packages_by_student_id.get(student_id, []),
                },
            )

        return items, total

    async def find_expired_holds(self, now: datetime) -> list[Booking]:
        stmt = select(Booking).options(selectinload(Booking.slot)).where(
            Booking.status == BookingStatusEnum.HOLD,
            Booking.hold_expires_at.is_not(None),
            Booking.hold_expires_at <= now,
        )
        return (await self.session.scalars(stmt)).all()

    async def get_active_booking_for_slot(self, slot_id: UUID) -> Booking | None:
        """Return active booking (HOLD/CONFIRMED) for slot if present."""
        stmt = (
            select(Booking)
            .where(
                Booking.slot_id == slot_id,
                Booking.status.in_((BookingStatusEnum.HOLD, BookingStatusEnum.CONFIRMED)),
            )
            .order_by(Booking.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def get_reschedule_successor(self, booking_id: UUID) -> Booking | None:
        stmt = (
            select(Booking)
            .options(selectinload(Booking.slot), selectinload(Booking.package))
            .where(Booking.rescheduled_from_booking_id == booking_id)
            .order_by(Booking.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def save(self, booking: Booking) -> Booking:
        await self.session.flush()
        return booking
