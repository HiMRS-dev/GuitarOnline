"""Admin schemas."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    BookingStatusEnum,
    SlotBookingAggregateStatusEnum,
    SlotStatusEnum,
    TeacherStatusEnum,
)
from app.shared.utils import ensure_utc


class AdminActionCreate(BaseModel):
    """Create admin action request."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "admin.teacher.verify",
                "target_type": "teacher_profile",
                "target_id": "9e0dc1b6-c3e0-43be-8f8d-f6f321f4f0db",
                "payload": {"reason": "manual_review_passed"},
            },
        },
    )

    action: str = Field(min_length=1, max_length=128)
    target_type: str = Field(min_length=1, max_length=128)
    target_id: str | None = Field(default=None, max_length=128)
    payload: dict = Field(default_factory=dict)


class AdminActionRead(BaseModel):
    """Admin action response schema."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "eb4fbb69-951f-4f4f-aaf6-ebfff510db5b",
                "admin_id": "8a937f92-0132-4691-b735-c224078afaef",
                "action": "admin.teacher.verify",
                "target_type": "teacher_profile",
                "target_id": "9e0dc1b6-c3e0-43be-8f8d-f6f321f4f0db",
                "payload": {"reason": "manual_review_passed"},
                "created_at": "2026-03-04T11:00:00+00:00",
                "updated_at": "2026-03-04T11:00:00+00:00",
            },
        },
    )

    id: UUID
    admin_id: UUID
    action: str
    target_type: str
    target_id: str | None
    payload: dict
    created_at: datetime
    updated_at: datetime


class AdminKpiOverviewRead(BaseModel):
    """Admin KPI snapshot across core domains."""

    generated_at: datetime

    users_total: int
    users_students: int
    users_teachers: int
    users_admins: int

    bookings_total: int
    bookings_hold: int
    bookings_confirmed: int
    bookings_canceled: int
    bookings_expired: int

    lessons_total: int
    lessons_scheduled: int
    lessons_completed: int
    lessons_canceled: int

    payments_total: int
    payments_pending: int
    payments_succeeded: int
    payments_failed: int
    payments_refunded: int
    payments_succeeded_amount: Decimal
    payments_refunded_amount: Decimal
    payments_net_amount: Decimal

    packages_total: int
    packages_active: int
    packages_expired: int
    packages_canceled: int


class AdminTeacherListItemRead(BaseModel):
    """Admin teacher list item with search/filter metadata."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "teacher_id": "8a937f92-0132-4691-b735-c224078afaef",
                "profile_id": "9e0dc1b6-c3e0-43be-8f8d-f6f321f4f0db",
                "email": "teacher@example.com",
                "display_name": "Alice Blues",
                "status": "verified",
                "verified": True,
                "is_active": True,
                "tags": ["jazz", "fingerstyle"],
                "created_at_utc": "2026-03-05T10:00:00+00:00",
                "updated_at_utc": "2026-03-05T10:15:00+00:00",
            },
        },
    )

    teacher_id: UUID
    profile_id: UUID
    email: str
    display_name: str
    status: TeacherStatusEnum
    verified: bool
    is_active: bool
    tags: list[str]
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminTeacherDetailRead(BaseModel):
    """Admin teacher detail with profile metadata and moderation fields."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "teacher_id": "8a937f92-0132-4691-b735-c224078afaef",
                "profile_id": "9e0dc1b6-c3e0-43be-8f8d-f6f321f4f0db",
                "email": "teacher@example.com",
                "display_name": "Alice Blues",
                "bio": "Fingerstyle and jazz guitar teacher.",
                "experience_years": 8,
                "status": "verified",
                "verified": True,
                "is_active": True,
                "tags": ["jazz", "fingerstyle"],
                "created_at_utc": "2026-03-05T10:00:00+00:00",
                "updated_at_utc": "2026-03-05T10:15:00+00:00",
            },
        },
    )

    teacher_id: UUID
    profile_id: UUID
    email: str
    display_name: str
    bio: str
    experience_years: int
    status: TeacherStatusEnum
    verified: bool
    is_active: bool
    tags: list[str]
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminSlotListItemRead(BaseModel):
    """Admin slot list item with aggregated booking status."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slot_id": "41fc173a-0a17-4ebf-8687-951714f1f55f",
                "teacher_id": "8a937f92-0132-4691-b735-c224078afaef",
                "created_by_admin_id": "c4ea1016-8586-4602-9fbe-c1100d2057a1",
                "start_at_utc": "2026-03-07T12:00:00+00:00",
                "end_at_utc": "2026-03-07T13:00:00+00:00",
                "slot_status": "booked",
                "booking_id": "6b6a1681-f4d1-47fc-b6de-d4f4f657f57d",
                "booking_status": "confirmed",
                "aggregated_booking_status": "confirmed",
                "created_at_utc": "2026-03-05T10:20:00+00:00",
                "updated_at_utc": "2026-03-05T10:25:00+00:00",
            },
        },
    )

    slot_id: UUID
    teacher_id: UUID
    created_by_admin_id: UUID
    start_at_utc: datetime
    end_at_utc: datetime
    slot_status: SlotStatusEnum
    booking_id: UUID | None
    booking_status: BookingStatusEnum | None
    aggregated_booking_status: SlotBookingAggregateStatusEnum
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminSlotCreateRequest(BaseModel):
    """Admin request schema for single slot creation."""

    teacher_id: UUID
    start_at_utc: datetime
    end_at_utc: datetime

    @field_validator("start_at_utc", "end_at_utc", mode="after")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        """Normalize incoming datetimes to UTC."""
        return ensure_utc(value)


class AdminSlotCreateRead(BaseModel):
    """Admin response schema for created slot."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slot_id": "41fc173a-0a17-4ebf-8687-951714f1f55f",
                "teacher_id": "8a937f92-0132-4691-b735-c224078afaef",
                "created_by_admin_id": "c4ea1016-8586-4602-9fbe-c1100d2057a1",
                "start_at_utc": "2026-03-07T12:00:00+00:00",
                "end_at_utc": "2026-03-07T13:00:00+00:00",
                "slot_status": "open",
                "created_at_utc": "2026-03-05T10:20:00+00:00",
                "updated_at_utc": "2026-03-05T10:20:00+00:00",
            },
        },
    )

    slot_id: UUID
    teacher_id: UUID
    created_by_admin_id: UUID
    start_at_utc: datetime
    end_at_utc: datetime
    slot_status: SlotStatusEnum
    created_at_utc: datetime
    updated_at_utc: datetime


class AdminSlotBlockRequest(BaseModel):
    """Admin request schema for slot blocking."""

    reason: str = Field(min_length=1, max_length=512)


class AdminSlotBlockRead(BaseModel):
    """Admin response schema for blocked slot state."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slot_id": "41fc173a-0a17-4ebf-8687-951714f1f55f",
                "slot_status": "blocked",
                "block_reason": "Teacher unavailable (sick leave)",
                "blocked_at_utc": "2026-03-05T12:30:00+00:00",
                "blocked_by_admin_id": "c4ea1016-8586-4602-9fbe-c1100d2057a1",
                "updated_at_utc": "2026-03-05T12:30:00+00:00",
            },
        },
    )

    slot_id: UUID
    slot_status: SlotStatusEnum
    block_reason: str | None
    blocked_at_utc: datetime | None
    blocked_by_admin_id: UUID | None
    updated_at_utc: datetime


class AdminSlotBulkCreateRequest(BaseModel):
    """Admin request schema for bulk slot generation."""

    teacher_id: UUID
    date_from_utc: date
    date_to_utc: date
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start_time_utc: time
    end_time_utc: time
    slot_duration_minutes: int = Field(ge=1, le=720)

    @field_validator("weekdays", mode="after")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        normalized = sorted(set(value))
        if any(day < 0 or day > 6 for day in normalized):
            raise ValueError("weekdays must contain values in range 0..6")
        return normalized

    @field_validator("start_time_utc", "end_time_utc", mode="after")
    @classmethod
    def normalize_time_precision(cls, value: time) -> time:
        return value.replace(second=0, microsecond=0)


class AdminSlotBulkCreateSkippedItemRead(BaseModel):
    """Skipped candidate slot in bulk create response."""

    start_at_utc: datetime
    end_at_utc: datetime
    reason: str


class AdminSlotBulkCreateRead(BaseModel):
    """Bulk slot creation response summary."""

    created_count: int
    skipped_count: int
    created_slot_ids: list[UUID]
    skipped: list[AdminSlotBulkCreateSkippedItemRead]


class AdminOperationsOverviewRead(BaseModel):
    """Operational snapshot for admin runbook checks."""

    generated_at: datetime
    max_retries: int
    outbox_pending: int
    outbox_failed_retryable: int
    outbox_failed_dead_letter: int
    notifications_failed: int
    stale_booking_holds: int
    overdue_active_packages: int
