"""Admin repository layer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    BookingStatusEnum,
    LessonStatusEnum,
    PackageStatusEnum,
    PaymentStatusEnum,
    RoleEnum,
)
from app.modules.admin.models import AdminAction
from app.modules.billing.models import LessonPackage, Payment
from app.modules.booking.models import Booking
from app.modules.identity.models import Role, User
from app.modules.lessons.models import Lesson
from app.shared.utils import utc_now


class AdminRepository:
    """DB operations for admin domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_action(
        self,
        admin_id: UUID,
        action: str,
        target_type: str,
        target_id: str | None,
        payload: dict,
    ) -> AdminAction:
        action_obj = AdminAction(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )
        self.session.add(action_obj)
        await self.session.flush()
        return action_obj

    async def list_actions(self, limit: int, offset: int) -> tuple[list[AdminAction], int]:
        base_stmt: Select[tuple[AdminAction]] = select(AdminAction)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(AdminAction.created_at.desc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def get_kpi_overview(self) -> dict[str, datetime | int | Decimal]:
        role_counts = await self._count_users_by_role()
        booking_counts = await self._count_bookings_by_status()
        lesson_counts = await self._count_lessons_by_status()
        payment_counts = await self._count_payments_by_status()
        package_counts = await self._count_packages_by_status()

        payments_succeeded_amount = await self._sum_payments_by_status(PaymentStatusEnum.SUCCEEDED)
        payments_refunded_amount = await self._sum_payments_by_status(PaymentStatusEnum.REFUNDED)

        users_students = role_counts.get(RoleEnum.STUDENT, 0)
        users_teachers = role_counts.get(RoleEnum.TEACHER, 0)
        users_admins = role_counts.get(RoleEnum.ADMIN, 0)

        bookings_hold = booking_counts.get(BookingStatusEnum.HOLD, 0)
        bookings_confirmed = booking_counts.get(BookingStatusEnum.CONFIRMED, 0)
        bookings_canceled = booking_counts.get(BookingStatusEnum.CANCELED, 0)
        bookings_expired = booking_counts.get(BookingStatusEnum.EXPIRED, 0)

        lessons_scheduled = lesson_counts.get(LessonStatusEnum.SCHEDULED, 0)
        lessons_completed = lesson_counts.get(LessonStatusEnum.COMPLETED, 0)
        lessons_canceled = lesson_counts.get(LessonStatusEnum.CANCELED, 0)

        payments_pending = payment_counts.get(PaymentStatusEnum.PENDING, 0)
        payments_succeeded = payment_counts.get(PaymentStatusEnum.SUCCEEDED, 0)
        payments_failed = payment_counts.get(PaymentStatusEnum.FAILED, 0)
        payments_refunded = payment_counts.get(PaymentStatusEnum.REFUNDED, 0)

        packages_active = package_counts.get(PackageStatusEnum.ACTIVE, 0)
        packages_expired = package_counts.get(PackageStatusEnum.EXPIRED, 0)
        packages_canceled = package_counts.get(PackageStatusEnum.CANCELED, 0)

        return {
            "generated_at": utc_now(),
            "users_total": users_students + users_teachers + users_admins,
            "users_students": users_students,
            "users_teachers": users_teachers,
            "users_admins": users_admins,
            "bookings_total": (
                bookings_hold + bookings_confirmed + bookings_canceled + bookings_expired
            ),
            "bookings_hold": bookings_hold,
            "bookings_confirmed": bookings_confirmed,
            "bookings_canceled": bookings_canceled,
            "bookings_expired": bookings_expired,
            "lessons_total": lessons_scheduled + lessons_completed + lessons_canceled,
            "lessons_scheduled": lessons_scheduled,
            "lessons_completed": lessons_completed,
            "lessons_canceled": lessons_canceled,
            "payments_total": (
                payments_pending + payments_succeeded + payments_failed + payments_refunded
            ),
            "payments_pending": payments_pending,
            "payments_succeeded": payments_succeeded,
            "payments_failed": payments_failed,
            "payments_refunded": payments_refunded,
            "payments_succeeded_amount": payments_succeeded_amount,
            "payments_refunded_amount": payments_refunded_amount,
            "payments_net_amount": payments_succeeded_amount - payments_refunded_amount,
            "packages_total": packages_active + packages_expired + packages_canceled,
            "packages_active": packages_active,
            "packages_expired": packages_expired,
            "packages_canceled": packages_canceled,
        }

    async def _count_users_by_role(self) -> dict[RoleEnum, int]:
        stmt = (
            select(Role.name, func.count(User.id))
            .join(User, User.role_id == Role.id)
            .group_by(Role.name)
        )
        rows = (await self.session.execute(stmt)).all()
        return {role_name: int(count) for role_name, count in rows}

    async def _count_bookings_by_status(self) -> dict[BookingStatusEnum, int]:
        stmt = select(Booking.status, func.count(Booking.id)).group_by(Booking.status)
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _count_lessons_by_status(self) -> dict[LessonStatusEnum, int]:
        stmt = select(Lesson.status, func.count(Lesson.id)).group_by(Lesson.status)
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _count_payments_by_status(self) -> dict[PaymentStatusEnum, int]:
        stmt = select(Payment.status, func.count(Payment.id)).group_by(Payment.status)
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _count_packages_by_status(self) -> dict[PackageStatusEnum, int]:
        stmt = select(LessonPackage.status, func.count(LessonPackage.id)).group_by(
            LessonPackage.status,
        )
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _sum_payments_by_status(self, status: PaymentStatusEnum) -> Decimal:
        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == status)
        value = (await self.session.scalar(stmt)) or Decimal("0")
        return Decimal(value)
