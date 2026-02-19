"""Booking ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.core.enums import BookingStatusEnum

if TYPE_CHECKING:
    from app.modules.billing.models import LessonPackage
    from app.modules.identity.models import User
    from app.modules.scheduling.models import AvailabilitySlot


class Booking(BaseModelMixin, Base):
    """Lesson booking model."""

    __tablename__ = "bookings"

    slot_id: Mapped[UUID] = mapped_column(
        ForeignKey("availability_slots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    package_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("lesson_packages.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[BookingStatusEnum] = mapped_column(
        SAEnum(BookingStatusEnum, name="booking_status_enum", native_enum=False),
        default=BookingStatusEnum.HOLD,
        nullable=False,
        index=True,
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    refund_returned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    rescheduled_from_booking_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
    )

    slot: Mapped["AvailabilitySlot"] = relationship(back_populates="booking")
    student: Mapped["User"] = relationship(back_populates="bookings_as_student", foreign_keys=[student_id])
    teacher: Mapped["User"] = relationship(back_populates="bookings_as_teacher", foreign_keys=[teacher_id])
    package: Mapped["LessonPackage | None"] = relationship(back_populates="bookings")
