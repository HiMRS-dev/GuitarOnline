"""Admin schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminActionCreate(BaseModel):
    """Create admin action request."""

    action: str = Field(min_length=1, max_length=128)
    target_type: str = Field(min_length=1, max_length=128)
    target_id: str | None = Field(default=None, max_length=128)
    payload: dict = Field(default_factory=dict)


class AdminActionRead(BaseModel):
    """Admin action response schema."""

    model_config = ConfigDict(from_attributes=True)

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
