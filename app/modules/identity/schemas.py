"""Identity schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import RoleEnum


class RoleRead(BaseModel):
    """Role response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: RoleEnum


class UserCreate(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str = Field(default="UTC", max_length=64)
    role: RoleEnum = RoleEnum.STUDENT


class LoginRequest(BaseModel):
    """Credentials for login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Refresh token payload."""

    refresh_token: str


class TokenPair(BaseModel):
    """Access + refresh JWT response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    """User output schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    timezone: str
    is_active: bool
    role: RoleRead
    created_at: datetime
    updated_at: datetime
