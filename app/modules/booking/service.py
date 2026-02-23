"""Booking business logic layer."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.enums import (
    BookingStatusEnum,
    LessonStatusEnum,
    PackageStatusEnum,
    RoleEnum,
    SlotStatusEnum,
)
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.booking.models import Booking
from app.modules.booking.repository import BookingRepository
from app.modules.booking.schemas import (
    BookingCancelRequest,
    BookingHoldRequest,
    BookingRescheduleRequest,
)
from app.modules.identity.models import User
from app.modules.lessons.repository import LessonsRepository
from app.modules.scheduling.repository import SchedulingRepository
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)
from app.shared.utils import utc_now

settings = get_settings()


class BookingService:
    """Booking domain service with hold/confirm/cancel rules."""

    def __init__(
        self,
        booking_repository: BookingRepository,
        scheduling_repository: SchedulingRepository,
        billing_repository: BillingRepository,
        lessons_repository: LessonsRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.booking_repository = booking_repository
        self.scheduling_repository = scheduling_repository
        self.billing_repository = billing_repository
        self.lessons_repository = lessons_repository
        self.audit_repository = audit_repository

    def _validate_actor_access(self, booking: Booking, actor: User) -> None:
        if actor.role.name == RoleEnum.ADMIN:
            return
        if actor.role.name == RoleEnum.STUDENT and booking.student_id == actor.id:
            return
        if actor.role.name == RoleEnum.TEACHER and booking.teacher_id == actor.id:
            return
        raise UnauthorizedException("You cannot manage this booking")

    async def _ensure_lesson_for_confirmed_booking(self, booking: Booking) -> None:
        """Create lesson for confirmed booking if it does not exist yet."""
        lesson = await self.lessons_repository.get_lesson_by_booking_id(booking.id)
        if lesson is not None:
            return

        lesson = await self.lessons_repository.create_lesson(
            booking_id=booking.id,
            student_id=booking.student_id,
            teacher_id=booking.teacher_id,
            scheduled_start_at=booking.slot.start_at,
            scheduled_end_at=booking.slot.end_at,
            topic=None,
            notes=None,
        )
        await self.audit_repository.create_outbox_event(
            aggregate_type="lesson",
            aggregate_id=str(lesson.id),
            event_type="lesson.created",
            payload={
                "lesson_id": str(lesson.id),
                "booking_id": str(booking.id),
                "student_id": str(booking.student_id),
                "teacher_id": str(booking.teacher_id),
            },
        )

    async def _cancel_lesson_for_booking(self, booking: Booking, reason: str | None) -> None:
        """Cancel linked lesson if it exists and is not already canceled."""
        lesson = await self.lessons_repository.get_lesson_by_booking_id(booking.id)
        if lesson is None or lesson.status == LessonStatusEnum.CANCELED:
            return

        await self.lessons_repository.update_lesson(lesson, status=LessonStatusEnum.CANCELED)
        await self.audit_repository.create_outbox_event(
            aggregate_type="lesson",
            aggregate_id=str(lesson.id),
            event_type="lesson.canceled",
            payload={
                "lesson_id": str(lesson.id),
                "booking_id": str(booking.id),
                "student_id": str(booking.student_id),
                "teacher_id": str(booking.teacher_id),
                "reason": reason,
            },
        )

    async def hold_booking(self, payload: BookingHoldRequest, actor: User) -> Booking:
        """Create booking in HOLD status for 10 minutes."""
        if actor.role.name != RoleEnum.STUDENT:
            raise UnauthorizedException("Only students can hold bookings")

        slot = await self.scheduling_repository.get_slot_by_id(payload.slot_id)
        if slot is None:
            raise NotFoundException("Slot not found")
        if slot.status != SlotStatusEnum.OPEN:
            raise BusinessRuleException("Slot is not available")
        if slot.start_at <= utc_now():
            raise BusinessRuleException("Cannot book a slot in the past")

        package = await self.billing_repository.get_package_by_id(payload.package_id)
        if package is None:
            raise NotFoundException("Package not found")
        if package.student_id != actor.id:
            raise UnauthorizedException("Package does not belong to current student")
        if package.status != PackageStatusEnum.ACTIVE:
            raise BusinessRuleException("Package is not active")
        if package.expires_at <= utc_now():
            raise BusinessRuleException("Package is expired")
        if package.lessons_left <= 0:
            raise BusinessRuleException("No lessons left in package")

        hold_expires_at = utc_now() + timedelta(minutes=settings.booking_hold_minutes)
        await self.scheduling_repository.set_slot_status(slot, SlotStatusEnum.HOLD)

        booking = await self.booking_repository.create_booking_hold(
            slot_id=slot.id,
            student_id=actor.id,
            teacher_id=slot.teacher_id,
            package_id=package.id,
            hold_expires_at=hold_expires_at,
        )

        await self.audit_repository.create_outbox_event(
            aggregate_type="booking",
            aggregate_id=str(booking.id),
            event_type="booking.hold.created",
            payload={
                "booking_id": str(booking.id),
                "slot_id": str(slot.id),
                "student_id": str(actor.id),
            },
        )

        return booking

    async def confirm_booking(self, booking_id: UUID, actor: User) -> Booking:
        """Confirm held booking and consume lesson from package."""
        booking = await self.booking_repository.get_booking_by_id(booking_id)
        if booking is None:
            raise NotFoundException("Booking not found")

        self._validate_actor_access(booking, actor)

        if booking.status != BookingStatusEnum.HOLD:
            raise ConflictException("Only HOLD booking can be confirmed")

        if booking.hold_expires_at is None or booking.hold_expires_at <= utc_now():
            booking.status = BookingStatusEnum.EXPIRED
            await self.scheduling_repository.set_slot_status(booking.slot, SlotStatusEnum.OPEN)
            await self.booking_repository.save(booking)
            raise BusinessRuleException("Booking hold has expired")

        if booking.package_id is None:
            raise BusinessRuleException("Booking package is required")

        package = await self.billing_repository.get_package_by_id(booking.package_id)
        if package is None:
            raise NotFoundException("Package not found")

        if package.status != PackageStatusEnum.ACTIVE or package.expires_at <= utc_now():
            raise BusinessRuleException("Package is inactive or expired")
        if package.lessons_left <= 0:
            raise BusinessRuleException("No lessons left")

        await self.billing_repository.consume_package_lesson(package)

        booking.status = BookingStatusEnum.CONFIRMED
        booking.confirmed_at = utc_now()
        booking.hold_expires_at = None
        await self.scheduling_repository.set_slot_status(booking.slot, SlotStatusEnum.BOOKED)
        await self.booking_repository.save(booking)

        await self.audit_repository.create_outbox_event(
            aggregate_type="booking",
            aggregate_id=str(booking.id),
            event_type="booking.confirmed",
            payload={
                "booking_id": str(booking.id),
                "student_id": str(booking.student_id),
                "slot_id": str(booking.slot_id),
            },
        )
        await self._ensure_lesson_for_confirmed_booking(booking)

        return booking

    async def cancel_booking(
        self,
        booking_id: UUID,
        payload: BookingCancelRequest,
        actor: User,
    ) -> Booking:
        """Cancel booking with refund rules based on 24h window."""
        booking = await self.booking_repository.get_booking_by_id(booking_id)
        if booking is None:
            raise NotFoundException("Booking not found")

        self._validate_actor_access(booking, actor)

        if booking.status in (BookingStatusEnum.CANCELED, BookingStatusEnum.EXPIRED):
            raise ConflictException("Booking already canceled or expired")

        now = utc_now()
        refund_returned = False

        if booking.status == BookingStatusEnum.CONFIRMED and booking.package_id is not None:
            package = await self.billing_repository.get_package_by_id(booking.package_id)
            if package is None:
                raise NotFoundException("Package not found")

            hours_before_lesson = (booking.slot.start_at - now).total_seconds() / 3600
            if hours_before_lesson > settings.booking_refund_window_hours:
                await self.billing_repository.return_package_lesson(package)
                refund_returned = True

        booking.status = BookingStatusEnum.CANCELED
        booking.canceled_at = now
        booking.cancellation_reason = payload.reason
        booking.refund_returned = refund_returned

        if booking.slot.start_at > now:
            await self.scheduling_repository.set_slot_status(booking.slot, SlotStatusEnum.OPEN)

        await self.booking_repository.save(booking)

        await self.audit_repository.create_outbox_event(
            aggregate_type="booking",
            aggregate_id=str(booking.id),
            event_type="booking.canceled",
            payload={
                "booking_id": str(booking.id),
                "student_id": str(booking.student_id),
                "slot_id": str(booking.slot_id),
                "refund_returned": refund_returned,
            },
        )
        await self._cancel_lesson_for_booking(booking, payload.reason)

        return booking

    async def reschedule_booking(
        self,
        booking_id: UUID,
        payload: BookingRescheduleRequest,
        actor: User,
    ) -> Booking:
        """Reschedule as cancel + new booking."""
        old_booking = await self.cancel_booking(
            booking_id=booking_id,
            payload=BookingCancelRequest(reason="Rescheduled by user"),
            actor=actor,
        )

        if old_booking.package_id is None:
            raise BusinessRuleException("Booking has no package for reschedule")

        new_hold = await self.hold_booking(
            BookingHoldRequest(slot_id=payload.new_slot_id, package_id=old_booking.package_id),
            actor,
        )
        new_booking = await self.confirm_booking(new_hold.id, actor)
        new_booking.rescheduled_from_booking_id = old_booking.id
        await self.booking_repository.save(new_booking)

        await self.audit_repository.create_outbox_event(
            aggregate_type="booking",
            aggregate_id=str(new_booking.id),
            event_type="booking.rescheduled",
            payload={
                "new_booking_id": str(new_booking.id),
                "old_booking_id": str(old_booking.id),
                "student_id": str(new_booking.student_id),
            },
        )

        return new_booking

    async def expire_holds(self, actor: User) -> int:
        """Expire stale HOLD bookings and release slots."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can run hold expiration")

        now = utc_now()
        holds = await self.booking_repository.find_expired_holds(now)
        for booking in holds:
            booking.status = BookingStatusEnum.EXPIRED
            await self.scheduling_repository.set_slot_status(booking.slot, SlotStatusEnum.OPEN)
            await self.audit_repository.create_outbox_event(
                aggregate_type="booking",
                aggregate_id=str(booking.id),
                event_type="booking.hold.expired",
                payload={"booking_id": str(booking.id), "slot_id": str(booking.slot_id)},
            )
        return len(holds)

    async def list_bookings(
        self,
        actor: User,
        limit: int,
        offset: int,
    ) -> tuple[list[Booking], int]:
        """List bookings for actor according to role."""
        return await self.booking_repository.list_bookings(actor.id, actor.role.name, limit, offset)


async def get_booking_service(session: AsyncSession = Depends(get_db_session)) -> BookingService:
    """Dependency provider for booking service."""
    return BookingService(
        booking_repository=BookingRepository(session),
        scheduling_repository=SchedulingRepository(session),
        billing_repository=BillingRepository(session),
        lessons_repository=LessonsRepository(session),
        audit_repository=AuditRepository(session),
    )
