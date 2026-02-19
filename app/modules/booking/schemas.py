"""Booking schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import BookingStatusEnum


class BookingHoldRequest(BaseModel):
    """Create booking hold request."""

    slot_id: UUID
    package_id: UUID


class BookingCancelRequest(BaseModel):
    """Cancel booking request."""

    reason: str | None = Field(default=None, max_length=512)


class BookingRescheduleRequest(BaseModel):
    """Reschedule booking request."""

    new_slot_id: UUID


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
