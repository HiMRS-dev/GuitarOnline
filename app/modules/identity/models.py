"""Identity ORM models."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.core.enums import RoleEnum

if TYPE_CHECKING:
    from app.modules.booking.models import Booking
    from app.modules.notifications.models import Notification
    from app.modules.teachers.models import TeacherProfile


_FULL_NAME_BY_EMAIL: dict[str, str] = {
    "bootstrap-admin@guitaronline.dev": "Волков Алексей Николаевич",
    "demo-admin@guitaronline.dev": "Иванов Алексей Петрович",
    "demo-teacher-1@guitaronline.dev": "Петров Сергей Андреевич",
    "demo-teacher-2@guitaronline.dev": "Смирнов Павел Игоревич",
    "demo-teacher-3@guitaronline.dev": "Кузнецов Дмитрий Олегович",
    "demo-student-1@guitaronline.dev": "Новиков Илья Сергеевич",
    "demo-student-2@guitaronline.dev": "Васильев Артём Николаевич",
    "demo-student-3@guitaronline.dev": "Фёдоров Максим Андреевич",
    "demo-student-4@guitaronline.dev": "Попов Егор Павлович",
    "demo-student-5@guitaronline.dev": "Лебедев Кирилл Олегович",
    "smoke-admin-1@guitaronline.dev": "Морозов Артём Ильич",
    "smoke-teacher-1@guitaronline.dev": "Никитин Егор Павлович",
    "smoke-student-1@guitaronline.dev": "Фролов Кирилл Денисович",
    "smoke-student-2@guitaronline.dev": "Белов Матвей Сергеевич",
    "synthetic-ops-admin@guitaronline.dev": "Орлов Максим Игоревич",
    "synthetic-ops-teacher@guitaronline.dev": "Ковалёв Павел Андреевич",
    "synthetic-ops-student@guitaronline.dev": "Соколов Илья Дмитриевич",
}

_FULL_NAME_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("deploy-smoke-admin-", "Демидов Артём Сергеевич"),
)


def build_default_full_name(email: str) -> str:
    """Provide a deterministic default full name for system-created accounts."""

    normalized = email.strip().lower()
    if not normalized:
        return "Иванов Алексей Петрович"

    exact_match = _FULL_NAME_BY_EMAIL.get(normalized)
    if exact_match is not None:
        return exact_match

    for prefix, full_name in _FULL_NAME_BY_PREFIX:
        if normalized.startswith(prefix):
            return full_name

    local_part = normalized.split("@", 1)[0]
    if "teacher" in local_part:
        return "Ковалёв Павел Андреевич"
    if "student" in local_part:
        return "Соколов Илья Дмитриевич"
    if "admin" in local_part:
        return "Волков Алексей Николаевич"

    tokens = [token for token in re.split(r"[^a-z0-9]+", local_part) if token]
    if tokens:
        capitalized = " ".join(token.capitalize() for token in tokens[:3])
        return f"Иванов {capitalized} Петрович"[:255]

    return "Иванов Алексей Петрович"


class Role(BaseModelMixin, Base):
    """System role model."""

    __tablename__ = "roles"

    name: Mapped[RoleEnum] = mapped_column(
        SAEnum(RoleEnum, name="role_enum", native_enum=False),
        unique=True,
        nullable=False,
    )

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(BaseModelMixin, Base):
    """Platform user model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[Role] = relationship(back_populates="users")

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    teacher_profile: Mapped[TeacherProfile | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    bookings_as_student: Mapped[list[Booking]] = relationship(
        back_populates="student",
        foreign_keys="Booking.student_id",
    )
    bookings_as_teacher: Mapped[list[Booking]] = relationship(
        back_populates="teacher",
        foreign_keys="Booking.teacher_id",
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")


class RefreshToken(BaseModelMixin, Base):
    """Refresh token persistence for revoke/rotation support."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
