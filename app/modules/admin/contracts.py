"""Admin API contract DTOs for frontend integration."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.enums import (
    BookingStatusEnum,
    LessonStatusEnum,
    PackageStatusEnum,
    PaymentStatusEnum,
    RoleEnum,
    SlotStatusEnum,
    TeacherStatusEnum,
)


class AdminTeacherDTO(BaseModel):
    """Teacher entity contract for admin UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    user_id: UUID
    email: EmailStr
    display_name: str
    bio: str
    experience_years: int
    status: TeacherStatusEnum
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminSlotDTO(BaseModel):
    """Availability slot contract for admin UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    teacher_id: UUID
    created_by_admin_id: UUID
    start_at_utc: datetime
    end_at_utc: datetime
    status: SlotStatusEnum
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminBookingDTO(BaseModel):
    """Booking contract for admin UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    slot_id: UUID
    student_id: UUID
    teacher_id: UUID
    package_id: UUID | None
    status: BookingStatusEnum
    hold_expires_at_utc: datetime | None
    confirmed_at_utc: datetime | None
    canceled_at_utc: datetime | None
    cancellation_reason: str | None
    refund_returned: bool
    rescheduled_from_booking_id: UUID | None
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminPackageDTO(BaseModel):
    """Lesson package contract for admin UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    student_id: UUID
    lessons_total: int
    lessons_left: int
    lessons_reserved: int
    expires_at_utc: datetime
    status: PackageStatusEnum
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminPaymentDTO(BaseModel):
    """Payment contract for admin UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    package_id: UUID
    amount: Decimal
    currency: str
    status: PaymentStatusEnum
    external_reference: str | None
    paid_at_utc: datetime | None
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminStudentDTO(BaseModel):
    """Student entity contract for admin UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: EmailStr
    timezone: str
    is_active: bool
    role: RoleEnum
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminLessonDTO(BaseModel):
    """Lesson entity contract for admin UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    booking_id: UUID
    student_id: UUID
    teacher_id: UUID
    scheduled_start_at_utc: datetime
    scheduled_end_at_utc: datetime
    status: LessonStatusEnum
    topic: str | None
    notes: str | None
    created_at_utc: datetime
    updated_at_utc: datetime
