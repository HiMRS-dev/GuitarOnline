"""Lessons schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import LessonStatusEnum
from app.shared.utils import ensure_utc


class LessonCreate(BaseModel):
    """Create lesson request."""

    booking_id: UUID
    student_id: UUID
    teacher_id: UUID
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    topic: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("scheduled_start_at", "scheduled_end_at", mode="after")
    @classmethod
    def normalize_schedule_to_utc(cls, value: datetime) -> datetime:
        """Normalize lesson schedule datetimes to UTC."""
        return ensure_utc(value)


class LessonUpdate(BaseModel):
    """Update lesson request."""

    status: LessonStatusEnum | None = None
    topic: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class LessonRead(BaseModel):
    """Lesson response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    booking_id: UUID
    student_id: UUID
    teacher_id: UUID
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    status: LessonStatusEnum
    topic: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
