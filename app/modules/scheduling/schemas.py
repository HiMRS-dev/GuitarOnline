"""Scheduling schemas."""

from __future__ import annotations

from datetime import datetime
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
    created_by_admin_id: UUID
    start_at: datetime
    end_at: datetime
    status: SlotStatusEnum
    created_at: datetime
    updated_at: datetime
