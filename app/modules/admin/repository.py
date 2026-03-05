"""Admin repository layer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
    BookingStatusEnum,
    LessonStatusEnum,
    NotificationStatusEnum,
    OutboxStatusEnum,
    PackageStatusEnum,
    PaymentStatusEnum,
    RoleEnum,
    SlotStatusEnum,
    TeacherStatusEnum,
)
from app.modules.admin.models import AdminAction
from app.modules.audit.models import AuditLog, OutboxEvent
from app.modules.billing.models import LessonPackage, Payment
from app.modules.booking.models import Booking
from app.modules.identity.models import Role, User
from app.modules.lessons.models import Lesson
from app.modules.notifications.models import Notification
from app.modules.scheduling.models import AvailabilitySlot
from app.modules.teachers.models import TeacherProfile, TeacherProfileTag
from app.shared.utils import utc_now

ACTIVE_BOOKING_STATUSES: tuple[BookingStatusEnum, ...] = (
    BookingStatusEnum.HOLD,
    BookingStatusEnum.CONFIRMED,
)


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

    async def list_teachers(
        self,
        *,
        limit: int,
        offset: int,
        status: TeacherStatusEnum | None,
        verified: bool | None,
        q: str | None,
        tag: str | None,
    ) -> tuple[list[dict[str, object]], int]:
        """List teachers for admin scheduling and moderation flows."""
        normalized_q = q.strip() if q else None
        normalized_tag = tag.strip().lower() if tag else None

        base_stmt: Select[tuple[UUID]] = (
            select(TeacherProfile.id)
            .join(User, User.id == TeacherProfile.user_id)
            .join(Role, Role.id == User.role_id)
            .where(Role.name == RoleEnum.TEACHER)
        )

        if status is not None:
            base_stmt = base_stmt.where(TeacherProfile.status == status)
        if verified is not None:
            base_stmt = base_stmt.where(TeacherProfile.is_approved.is_(verified))
        if normalized_q:
            pattern = f"%{normalized_q}%"
            base_stmt = base_stmt.where(
                or_(
                    TeacherProfile.display_name.ilike(pattern),
                    User.email.ilike(pattern),
                ),
            )
        if normalized_tag:
            base_stmt = base_stmt.join(
                TeacherProfileTag,
                TeacherProfileTag.teacher_profile_id == TeacherProfile.id,
            ).where(func.lower(TeacherProfileTag.tag) == normalized_tag)

        teacher_ids_stmt = base_stmt.distinct()
        total_stmt = select(func.count()).select_from(teacher_ids_stmt.subquery())
        total = int((await self.session.scalar(total_stmt)) or 0)

        paged_ids_stmt = (
            teacher_ids_stmt.order_by(TeacherProfile.created_at.desc()).limit(limit).offset(offset)
        )
        teacher_profile_ids = list((await self.session.scalars(paged_ids_stmt)).all())
        if not teacher_profile_ids:
            return [], total

        profiles_stmt = (
            select(TeacherProfile)
            .where(TeacherProfile.id.in_(teacher_profile_ids))
            .options(
                selectinload(TeacherProfile.user),
                selectinload(TeacherProfile.tags),
            )
        )
        profiles = (await self.session.scalars(profiles_stmt)).all()
        profile_by_id = {profile.id: profile for profile in profiles}

        items: list[dict[str, object]] = []
        for profile_id in teacher_profile_ids:
            profile = profile_by_id.get(profile_id)
            if profile is None:
                continue

            serialized = self._serialize_teacher_profile(profile)
            if serialized is None:
                continue
            items.append(serialized)

        return items, total

    async def get_teacher_detail(self, *, teacher_id: UUID) -> dict[str, object] | None:
        """Get teacher detail by teacher user id."""
        profile = await self._get_teacher_profile_by_user_id(teacher_id=teacher_id)
        if profile is None:
            return None

        return self._serialize_teacher_profile(profile, include_profile_fields=True)

    async def verify_teacher(
        self,
        *,
        teacher_id: UUID,
        admin_id: UUID,
    ) -> dict[str, object] | None:
        """Verify teacher profile and write audit trail."""
        profile = await self._get_teacher_profile_by_user_id(
            teacher_id=teacher_id,
            lock_for_update=True,
        )
        if profile is None:
            return None

        user = profile.user
        if user is None:
            return None

        previous_status = profile.status
        previous_is_approved = profile.is_approved

        profile.status = TeacherStatusEnum.VERIFIED
        profile.is_approved = True

        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.teacher.verify",
                entity_type="teacher_profile",
                entity_id=str(profile.id),
                payload={
                    "teacher_id": str(profile.user_id),
                    "from_status": str(previous_status),
                    "to_status": str(profile.status),
                    "from_is_approved": previous_is_approved,
                    "to_is_approved": profile.is_approved,
                    "user_is_active": user.is_active,
                },
            ),
        )
        await self.session.flush()
        return self._serialize_teacher_profile(profile, include_profile_fields=True)

    async def disable_teacher(
        self,
        *,
        teacher_id: UUID,
        admin_id: UUID,
    ) -> dict[str, object] | None:
        """Disable teacher profile and user account and write audit trail."""
        profile = await self._get_teacher_profile_by_user_id(
            teacher_id=teacher_id,
            lock_for_update=True,
        )
        if profile is None:
            return None

        user = profile.user
        if user is None:
            return None

        previous_status = profile.status
        previous_is_approved = profile.is_approved
        previous_is_active = user.is_active

        profile.status = TeacherStatusEnum.DISABLED
        profile.is_approved = False
        user.is_active = False

        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.teacher.disable",
                entity_type="teacher_profile",
                entity_id=str(profile.id),
                payload={
                    "teacher_id": str(profile.user_id),
                    "from_status": str(previous_status),
                    "to_status": str(profile.status),
                    "from_is_approved": previous_is_approved,
                    "to_is_approved": profile.is_approved,
                    "from_user_is_active": previous_is_active,
                    "to_user_is_active": user.is_active,
                },
            ),
        )
        await self.session.flush()
        return self._serialize_teacher_profile(profile, include_profile_fields=True)

    async def _get_teacher_profile_by_user_id(
        self,
        *,
        teacher_id: UUID,
        lock_for_update: bool = False,
    ) -> TeacherProfile | None:
        stmt = (
            select(TeacherProfile)
            .join(User, User.id == TeacherProfile.user_id)
            .join(Role, Role.id == User.role_id)
            .where(
                TeacherProfile.user_id == teacher_id,
                Role.name == RoleEnum.TEACHER,
            )
            .options(
                selectinload(TeacherProfile.user),
                selectinload(TeacherProfile.tags),
            )
        )
        if lock_for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    def _serialize_teacher_profile(
        self,
        profile: TeacherProfile,
        *,
        include_profile_fields: bool = False,
    ) -> dict[str, object] | None:
        user = profile.user
        if user is None:
            return None

        tags = sorted({tag_row.tag for tag_row in profile.tags}, key=str.lower)
        data: dict[str, object] = {
            "teacher_id": profile.user_id,
            "profile_id": profile.id,
            "email": user.email,
            "display_name": profile.display_name,
            "status": profile.status,
            "verified": profile.is_approved,
            "is_active": user.is_active,
            "tags": tags,
            "created_at_utc": profile.created_at,
            "updated_at_utc": profile.updated_at,
        }
        if include_profile_fields:
            data["bio"] = profile.bio
            data["experience_years"] = profile.experience_years
        return data

    async def list_slots(
        self,
        *,
        teacher_id: UUID | None,
        from_utc: datetime | None,
        to_utc: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List slots with booking relation snapshot for admin views."""
        base_stmt: Select[tuple[AvailabilitySlot, UUID | None, BookingStatusEnum | None]] = (
            select(
                AvailabilitySlot,
                Booking.id.label("booking_id"),
                Booking.status.label("booking_status"),
            ).outerjoin(
                Booking,
                and_(
                    Booking.slot_id == AvailabilitySlot.id,
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                ),
            )
        )

        if teacher_id is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.teacher_id == teacher_id)
        if from_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at >= from_utc)
        if to_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at <= to_utc)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(AvailabilitySlot.start_at.asc()).limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).all()

        items: list[dict[str, object]] = []
        for slot, booking_id, booking_status in rows:
            items.append(
                {
                    "slot_id": slot.id,
                    "teacher_id": slot.teacher_id,
                    "created_by_admin_id": slot.created_by_admin_id,
                    "start_at_utc": slot.start_at,
                    "end_at_utc": slot.end_at,
                    "slot_status": slot.status,
                    "booking_id": booking_id,
                    "booking_status": booking_status,
                    "created_at_utc": slot.created_at,
                    "updated_at_utc": slot.updated_at,
                },
            )
        return items, total

    async def list_bookings(
        self,
        *,
        teacher_id: UUID | None,
        student_id: UUID | None,
        status: BookingStatusEnum | None,
        from_utc: datetime | None,
        to_utc: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List bookings with admin filters and slot-time range constraints."""
        base_stmt: Select[tuple[Booking, datetime, datetime]] = (
            select(
                Booking,
                AvailabilitySlot.start_at.label("slot_start_at_utc"),
                AvailabilitySlot.end_at.label("slot_end_at_utc"),
            ).join(
                AvailabilitySlot,
                AvailabilitySlot.id == Booking.slot_id,
            )
        )

        if teacher_id is not None:
            base_stmt = base_stmt.where(Booking.teacher_id == teacher_id)
        if student_id is not None:
            base_stmt = base_stmt.where(Booking.student_id == student_id)
        if status is not None:
            base_stmt = base_stmt.where(Booking.status == status)
        if from_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at >= from_utc)
        if to_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at <= to_utc)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = (
            base_stmt.order_by(AvailabilitySlot.start_at.asc(), Booking.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()

        items: list[dict[str, object]] = []
        for booking, slot_start_at_utc, slot_end_at_utc in rows:
            items.append(
                {
                    "booking_id": booking.id,
                    "slot_id": booking.slot_id,
                    "student_id": booking.student_id,
                    "teacher_id": booking.teacher_id,
                    "package_id": booking.package_id,
                    "status": booking.status,
                    "slot_start_at_utc": slot_start_at_utc,
                    "slot_end_at_utc": slot_end_at_utc,
                    "hold_expires_at_utc": booking.hold_expires_at,
                    "confirmed_at_utc": booking.confirmed_at,
                    "canceled_at_utc": booking.canceled_at,
                    "cancellation_reason": booking.cancellation_reason,
                    "refund_returned": booking.refund_returned,
                    "rescheduled_from_booking_id": booking.rescheduled_from_booking_id,
                    "created_at_utc": booking.created_at,
                    "updated_at_utc": booking.updated_at,
                },
            )
        return items, total

    async def list_packages(
        self,
        *,
        student_id: UUID | None,
        status: PackageStatusEnum | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List lesson packages for admin filters."""
        base_stmt: Select[tuple[LessonPackage]] = select(LessonPackage)
        if student_id is not None:
            base_stmt = base_stmt.where(LessonPackage.student_id == student_id)
        if status is not None:
            base_stmt = base_stmt.where(LessonPackage.status == status)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(LessonPackage.created_at.desc()).limit(limit).offset(offset)
        rows = (await self.session.scalars(stmt)).all()

        items: list[dict[str, object]] = []
        for package in rows:
            items.append(
                {
                    "package_id": package.id,
                    "student_id": package.student_id,
                    "lessons_total": package.lessons_total,
                    "lessons_left": package.lessons_left,
                    "price_amount": package.price_amount,
                    "price_currency": package.price_currency,
                    "expires_at_utc": package.expires_at,
                    "status": package.status,
                    "created_at_utc": package.created_at,
                    "updated_at_utc": package.updated_at,
                },
            )
        return items, total

    async def get_slot_by_id(self, slot_id: UUID) -> AvailabilitySlot | None:
        """Get slot by id for admin operations."""
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
        return await self.session.scalar(stmt)

    async def slot_has_bookings(self, slot_id: UUID) -> bool:
        """Return True if slot has at least one related booking row."""
        stmt = select(func.count(Booking.id)).where(Booking.slot_id == slot_id)
        return int((await self.session.scalar(stmt)) or 0) > 0

    async def delete_slot(self, *, slot: AvailabilitySlot, admin_id: UUID) -> None:
        """Delete slot and write audit log entry."""
        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.slot.delete",
                entity_type="availability_slot",
                entity_id=str(slot.id),
                payload={
                    "teacher_id": str(slot.teacher_id),
                    "start_at_utc": slot.start_at.isoformat(),
                    "end_at_utc": slot.end_at.isoformat(),
                    "status": str(slot.status),
                },
            ),
        )
        await self.session.delete(slot)
        await self.session.flush()

    async def block_slot(
        self,
        *,
        slot: AvailabilitySlot,
        reason: str,
        admin_id: UUID,
        blocked_at: datetime,
    ) -> AvailabilitySlot:
        """Mark slot as blocked and persist block metadata + audit."""
        previous_status = slot.status
        slot.status = SlotStatusEnum.BLOCKED
        slot.block_reason = reason
        slot.blocked_at = blocked_at
        slot.blocked_by_admin_id = admin_id

        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.slot.block",
                entity_type="availability_slot",
                entity_id=str(slot.id),
                payload={
                    "teacher_id": str(slot.teacher_id),
                    "from_status": str(previous_status),
                    "to_status": str(slot.status),
                    "reason": reason,
                    "blocked_at_utc": blocked_at.isoformat(),
                },
            ),
        )
        await self.session.flush()
        return slot

    async def list_slot_status_snapshots(
        self,
        *,
        from_utc: datetime | None,
        to_utc: datetime | None,
    ) -> list[dict[str, object]]:
        """Return slot/booking/lesson status snapshots for stats aggregation."""
        stmt = (
            select(
                AvailabilitySlot.id.label("slot_id"),
                AvailabilitySlot.status.label("slot_status"),
                Booking.status.label("booking_status"),
                Lesson.status.label("lesson_status"),
            )
            .outerjoin(
                Booking,
                and_(
                    Booking.slot_id == AvailabilitySlot.id,
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                ),
            )
            .outerjoin(Lesson, Lesson.booking_id == Booking.id)
        )
        if from_utc is not None:
            stmt = stmt.where(AvailabilitySlot.start_at >= from_utc)
        if to_utc is not None:
            stmt = stmt.where(AvailabilitySlot.start_at <= to_utc)

        rows = (await self.session.execute(stmt)).all()
        items: list[dict[str, object]] = []
        for row in rows:
            items.append(
                {
                    "slot_id": row.slot_id,
                    "slot_status": row.slot_status,
                    "booking_status": row.booking_status,
                    "lesson_status": row.lesson_status,
                },
            )
        return items

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
        lessons_completed = lesson_counts.get(LessonStatusEnum.COMPLETED, 0) + lesson_counts.get(
            LessonStatusEnum.NO_SHOW,
            0,
        )
        lessons_canceled = lesson_counts.get(LessonStatusEnum.CANCELED, 0)

        payments_pending = payment_counts.get(PaymentStatusEnum.PENDING, 0)
        payments_succeeded = payment_counts.get(PaymentStatusEnum.SUCCEEDED, 0)
        payments_failed = payment_counts.get(PaymentStatusEnum.FAILED, 0)
        payments_refunded = payment_counts.get(PaymentStatusEnum.REFUNDED, 0)

        packages_active = package_counts.get(PackageStatusEnum.ACTIVE, 0)
        packages_expired = package_counts.get(PackageStatusEnum.EXPIRED, 0)
        packages_depleted = package_counts.get(PackageStatusEnum.DEPLETED, 0)
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
            "packages_total": (
                packages_active + packages_expired + packages_depleted + packages_canceled
            ),
            "packages_active": packages_active,
            "packages_expired": packages_expired,
            "packages_depleted": packages_depleted,
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

    async def get_operations_overview(
        self,
        *,
        max_retries: int,
        now: datetime | None = None,
    ) -> dict[str, datetime | int]:
        snapshot_now = now or utc_now()

        outbox_pending = await self._count_outbox_by_status(OutboxStatusEnum.PENDING)
        outbox_failed_retryable = await self._count_failed_outbox(
            retryable=True,
            max_retries=max_retries,
        )
        outbox_failed_dead_letter = await self._count_failed_outbox(
            retryable=False,
            max_retries=max_retries,
        )
        notifications_failed = await self._count_notifications_by_status(
            NotificationStatusEnum.FAILED,
        )
        stale_booking_holds = await self._count_stale_booking_holds(snapshot_now)
        overdue_active_packages = await self._count_overdue_active_packages(snapshot_now)

        return {
            "generated_at": snapshot_now,
            "max_retries": max_retries,
            "outbox_pending": outbox_pending,
            "outbox_failed_retryable": outbox_failed_retryable,
            "outbox_failed_dead_letter": outbox_failed_dead_letter,
            "notifications_failed": notifications_failed,
            "stale_booking_holds": stale_booking_holds,
            "overdue_active_packages": overdue_active_packages,
        }

    async def _count_outbox_by_status(self, status: OutboxStatusEnum) -> int:
        stmt = select(func.count(OutboxEvent.id)).where(OutboxEvent.status == status)
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_failed_outbox(self, *, retryable: bool, max_retries: int) -> int:
        comparison = (
            OutboxEvent.retries < max_retries
            if retryable
            else OutboxEvent.retries >= max_retries
        )
        stmt = select(func.count(OutboxEvent.id)).where(
            OutboxEvent.status == OutboxStatusEnum.FAILED,
            comparison,
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_notifications_by_status(self, status: NotificationStatusEnum) -> int:
        stmt = select(func.count(Notification.id)).where(Notification.status == status)
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_stale_booking_holds(self, now: datetime) -> int:
        stmt = select(func.count(Booking.id)).where(
            Booking.status == BookingStatusEnum.HOLD,
            Booking.hold_expires_at.is_not(None),
            Booking.hold_expires_at <= now,
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_overdue_active_packages(self, now: datetime) -> int:
        stmt = select(func.count(LessonPackage.id)).where(
            LessonPackage.status == PackageStatusEnum.ACTIVE,
            LessonPackage.expires_at <= now,
        )
        return int((await self.session.scalar(stmt)) or 0)
