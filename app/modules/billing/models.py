"""Billing ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.core.enums import PackageStatusEnum, PaymentStatusEnum

if TYPE_CHECKING:
    from app.modules.booking.models import Booking
    from app.modules.identity.models import User


class LessonPackage(BaseModelMixin, Base):
    """Student lessons package."""

    __tablename__ = "lesson_packages"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lessons_total: Mapped[int] = mapped_column(nullable=False)
    lessons_left: Mapped[int] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[PackageStatusEnum] = mapped_column(
        SAEnum(PackageStatusEnum, name="package_status_enum", native_enum=False),
        default=PackageStatusEnum.ACTIVE,
        nullable=False,
    )

    student: Mapped[User] = relationship()
    bookings: Mapped[list[Booking]] = relationship(back_populates="package")
    payments: Mapped[list[Payment]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
    )


class Payment(BaseModelMixin, Base):
    """Payment model for billing transactions."""

    __tablename__ = "payments"

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("lesson_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SAEnum(PaymentStatusEnum, name="payment_status_enum", native_enum=False),
        default=PaymentStatusEnum.PENDING,
        nullable=False,
    )
    external_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    package: Mapped[LessonPackage] = relationship(back_populates="payments")
