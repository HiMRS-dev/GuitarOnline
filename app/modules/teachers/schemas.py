"""Teachers schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeacherProfileCreate(BaseModel):
    """Create teacher profile request."""

    user_id: UUID
    display_name: str = Field(min_length=2, max_length=128)
    bio: str = Field(default="", max_length=5000)
    experience_years: int = Field(default=0, ge=0, le=80)


class TeacherProfileUpdate(BaseModel):
    """Update teacher profile request."""

    display_name: str | None = Field(default=None, min_length=2, max_length=128)
    bio: str | None = Field(default=None, max_length=5000)
    experience_years: int | None = Field(default=None, ge=0, le=80)
    is_approved: bool | None = None


class TeacherProfileRead(BaseModel):
    """Teacher profile response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: str
    bio: str
    experience_years: int
    is_approved: bool
    created_at: datetime
    updated_at: datetime
