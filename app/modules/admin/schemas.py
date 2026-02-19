"""Admin schemas."""

from __future__ import annotations

from datetime import datetime
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
