"""Scheduling ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.core.enums import SlotStatusEnum

if TYPE_CHECKING:
    from app.modules.booking.models import Booking


class AvailabilitySlot(BaseModelMixin, Base):
    """Teacher availability slot created by admin."""

    __tablename__ = "availability_slots"
    __table_args__ = (
        Index(
            "ix_availability_slots_teacher_start_at",
            "teacher_id",
            "start_at",
        ),
    )

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[SlotStatusEnum] = mapped_column(
        SAEnum(SlotStatusEnum, name="slot_status_enum", native_enum=False),
        default=SlotStatusEnum.OPEN,
        nullable=False,
        index=True,
    )
    block_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_by_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    booking: Mapped[Booking | None] = relationship(back_populates="slot", uselist=False)
