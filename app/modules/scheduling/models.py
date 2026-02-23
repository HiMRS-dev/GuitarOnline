"""Scheduling ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.core.enums import SlotStatusEnum

if TYPE_CHECKING:
    from app.modules.booking.models import Booking


class AvailabilitySlot(BaseModelMixin, Base):
    """Teacher availability slot created by admin."""

    __tablename__ = "availability_slots"

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

    booking: Mapped[Booking | None] = relationship(back_populates="slot", uselist=False)
