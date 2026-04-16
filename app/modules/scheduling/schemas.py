"""Scheduling schemas."""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import SlotStatusEnum
from app.shared.utils import ensure_utc


class SlotCreate(BaseModel):
    """Create availability slot request."""

    teacher_id: UUID
    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at", mode="after")
    @classmethod
    def normalize_datetime_to_utc(cls, value: datetime) -> datetime:
        """Normalize incoming datetimes to UTC."""
        return ensure_utc(value)


class SlotRead(BaseModel):
    """Availability slot response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_id: UUID
    teacher_full_name: str | None = None
    created_by_admin_id: UUID
    start_at: datetime
    end_at: datetime
    status: SlotStatusEnum
    created_at: datetime
    updated_at: datetime


class TeacherWeeklyScheduleWindowRead(BaseModel):
    """Teacher weekly schedule window in local timezone with Moscow projection."""

    schedule_window_id: UUID
    weekday: int
    start_local_time: time
    end_local_time: time
    moscow_start_weekday: int
    moscow_end_weekday: int
    moscow_start_time: time
    moscow_end_time: time
    created_at_utc: datetime
    updated_at_utc: datetime


class TeacherWeeklyScheduleRead(BaseModel):
    """Teacher weekly schedule response."""

    teacher_id: UUID
    timezone: str
    windows: list[TeacherWeeklyScheduleWindowRead]
