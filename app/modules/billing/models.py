"""Billing ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
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
    __table_args__ = (
        Index("ix_lesson_packages_created_at", "created_at"),
        Index("ix_lesson_packages_status_created_at", "status", "created_at"),
    )

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lessons_total: Mapped[int] = mapped_column(nullable=False)
    lessons_left: Mapped[int] = mapped_column(nullable=False)
    lessons_reserved: Mapped[int] = mapped_column(default=0, nullable=False)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
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
    __table_args__ = (
        Index("ix_payments_status_created_at", "status", "created_at"),
        Index("ix_payments_package_status_created_at", "package_id", "status", "created_at"),
    )

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("lesson_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False, default="manual_paid")
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SAEnum(PaymentStatusEnum, name="payment_status_enum", native_enum=False),
        default=PaymentStatusEnum.PENDING,
        nullable=False,
    )
    external_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    package: Mapped[LessonPackage] = relationship(back_populates="payments")
