"""Notifications schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import NotificationStatusEnum


class NotificationCreate(BaseModel):
    """Create notification request."""

    user_id: UUID
    channel: str = Field(default="email", max_length=32)
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


class NotificationUpdateStatus(BaseModel):
    """Update notification status request."""

    status: NotificationStatusEnum


class NotificationRead(BaseModel):
    """Notification response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    channel: str
    title: str
    body: str
    status: NotificationStatusEnum
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime
