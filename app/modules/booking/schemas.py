"""Booking schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import BookingStatusEnum, PackageStatusEnum
from app.shared.utils import ensure_utc


class BookingHoldRequest(BaseModel):
    """Create booking hold request."""

    slot_id: UUID
    package_id: UUID
    start_at: datetime | None = None
    end_at: datetime | None = None

    @field_validator("start_at", "end_at", mode="after")
    @classmethod
    def normalize_optional_datetime_to_utc(cls, value: datetime | None) -> datetime | None:
        """Normalize optional incoming datetimes to UTC."""
        if value is None:
            return None
        return ensure_utc(value)


class BookingCancelRequest(BaseModel):
    """Cancel booking request."""

    reason: str | None = Field(default=None, max_length=512)


class BookingRescheduleRequest(BaseModel):
    """Reschedule booking request."""

    new_slot_id: UUID
    reason: str | None = Field(default=None, max_length=512)


class BookingRead(BaseModel):
    """Booking response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slot_id: UUID
    student_id: UUID
    teacher_id: UUID
    package_id: UUID | None
    status: BookingStatusEnum
    hold_expires_at: datetime | None
    confirmed_at: datetime | None
    canceled_at: datetime | None
    cancellation_reason: str | None
    refund_returned: bool
    rescheduled_from_booking_id: UUID | None
    created_at: datetime
    updated_at: datetime


class TeacherStudentPackageBalanceRead(BaseModel):
    """Teacher-facing package balance snapshot for one student."""

    package_id: UUID
    status: PackageStatusEnum
    lessons_total: int
    lessons_left: int
    lessons_reserved: int
    lessons_available: int
    expires_at: datetime


class TeacherStudentListItemRead(BaseModel):
    """Teacher-facing active student snapshot with package balances."""

    student_id: UUID
    student_email: str
    student_full_name: str
    active_bookings_count: int
    last_booking_at: datetime
    packages: list[TeacherStudentPackageBalanceRead]
