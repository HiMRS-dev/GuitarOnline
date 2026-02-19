"""Audit schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import OutboxStatusEnum


class AuditLogCreate(BaseModel):
    """Create audit log request."""

    action: str
    entity_type: str
    entity_id: str | None = None
    payload: dict = Field(default_factory=dict)


class AuditLogRead(BaseModel):
    """Audit log response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    payload: dict
    created_at: datetime
    updated_at: datetime


class OutboxEventRead(BaseModel):
    """Outbox event response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict
    status: OutboxStatusEnum
    occurred_at: datetime
    processed_at: datetime | None
    retries: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
