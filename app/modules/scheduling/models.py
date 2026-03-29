"""Scheduling ORM models."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Time
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.core.enums import SlotStatusEnum

if TYPE_CHECKING:
    from app.modules.booking.models import Booking


class AvailabilitySlot(BaseModelMixin, Base):
    """Teacher availability slot created by admin."""

    __tablename__ = "availability_slots"
    __table_args__ = (
        Index(
            "ix_availability_slots_teacher_start_at",
            "teacher_id",
            "start_at",
        ),
    )

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[SlotStatusEnum] = mapped_column(
        SAEnum(SlotStatusEnum, name="slot_status_enum", native_enum=False),
        default=SlotStatusEnum.OPEN,
        nullable=False,
        index=True,
    )
    block_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_by_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    booking: Mapped[Booking | None] = relationship(back_populates="slot", uselist=False)


class TeacherWeeklyScheduleWindow(BaseModelMixin, Base):
    """Persistent weekly working window in teacher local timezone."""

    __tablename__ = "teacher_weekly_schedule_windows"
    __table_args__ = (
        CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="teacher_weekly_schedule_windows_weekday_range",
        ),
        CheckConstraint(
            "end_local_time > start_local_time",
            name="teacher_weekly_schedule_windows_time_range",
        ),
        Index(
            "ix_teacher_weekly_schedule_windows_teacher_weekday",
            "teacher_id",
            "weekday",
        ),
    )

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_local_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_local_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
