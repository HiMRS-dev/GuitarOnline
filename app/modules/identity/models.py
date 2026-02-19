"""Identity ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.core.enums import RoleEnum

if TYPE_CHECKING:
    from app.modules.booking.models import Booking
    from app.modules.notifications.models import Notification
    from app.modules.teachers.models import TeacherProfile


class Role(BaseModelMixin, Base):
    """System role model."""

    __tablename__ = "roles"

    name: Mapped[RoleEnum] = mapped_column(
        SAEnum(RoleEnum, name="role_enum", native_enum=False),
        unique=True,
        nullable=False,
    )

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(BaseModelMixin, Base):
    """Platform user model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    role: Mapped[Role] = relationship(back_populates="users")

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    teacher_profile: Mapped["TeacherProfile | None"] = relationship(back_populates="user", uselist=False)
    bookings_as_student: Mapped[list["Booking"]] = relationship(
        back_populates="student",
        foreign_keys="Booking.student_id",
    )
    bookings_as_teacher: Mapped[list["Booking"]] = relationship(
        back_populates="teacher",
        foreign_keys="Booking.teacher_id",
    )
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")


class RefreshToken(BaseModelMixin, Base):
    """Refresh token persistence for revoke/rotation support."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
