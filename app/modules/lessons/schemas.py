"""Lessons schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

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
    homework: str | None = None
    links: list[HttpUrl] | None = None
    meeting_url: HttpUrl | None = None
    recording_url: HttpUrl | None = None
    use_meeting_url_template: bool | None = None


class TeacherLessonReportRequest(BaseModel):
    """Teacher report payload for lesson outcomes and materials."""

    notes: str | None = None
    homework: str | None = None
    links: list[HttpUrl] = Field(default_factory=list, max_length=50)
    meeting_url: HttpUrl | None = None
    recording_url: HttpUrl | None = None
    use_meeting_url_template: bool | None = None


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
    consumed_at: datetime | None
    topic: str | None
    notes: str | None
    homework: str | None
    links: list[str] | None
    meeting_url: str | None
    recording_url: str | None
    created_at: datetime
    updated_at: datetime
