"""Scheduling schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import SlotStatusEnum


class SlotCreate(BaseModel):
    """Create availability slot request."""

    teacher_id: UUID
    start_at: datetime
    end_at: datetime


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
