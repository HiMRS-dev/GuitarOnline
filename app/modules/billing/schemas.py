"""Billing schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PackageStatusEnum, PaymentStatusEnum


class PackageCreate(BaseModel):
    """Create lesson package request."""

    student_id: UUID
    lessons_total: int = Field(ge=1)
    expires_at: datetime


class PackageRead(BaseModel):
    """Lesson package response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    lessons_total: int
    lessons_left: int
    expires_at: datetime
    status: PackageStatusEnum
    created_at: datetime
    updated_at: datetime


class PaymentCreate(BaseModel):
    """Create payment request."""

    package_id: UUID
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    external_reference: str | None = None


class PaymentUpdateStatus(BaseModel):
    """Update payment status request."""

    status: PaymentStatusEnum


class PaymentRead(BaseModel):
    """Payment response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    package_id: UUID
    amount: Decimal
    currency: str
    status: PaymentStatusEnum
    external_reference: str | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime
