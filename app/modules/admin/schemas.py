"""Admin schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TeacherStatusEnum


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
