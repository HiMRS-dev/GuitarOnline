"""Teachers ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.database import Base, BaseModelMixin
from app.core.enums import TeacherStatusEnum

if TYPE_CHECKING:
    from app.modules.identity.models import User


class TeacherStatusType(TypeDecorator[TeacherStatusEnum]):
    """Persist lowercase teacher-status values while tolerating legacy casing on read."""

    impl = String(16)
    cache_ok = True

    @staticmethod
    def _coerce(value: TeacherStatusEnum | str) -> TeacherStatusEnum:
        if isinstance(value, TeacherStatusEnum):
            return value

        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Teacher status cannot be empty.")
        return TeacherStatusEnum(normalized.lower())

    def process_bind_param(
        self,
        value: TeacherStatusEnum | str | None,
        dialect,
    ) -> str | None:
        if value is None:
            return None
        return self._coerce(value).value

    def process_result_value(self, value: str | None, dialect) -> TeacherStatusEnum | None:
        if value is None:
            return None
        return self._coerce(value)


class TeacherProfile(BaseModelMixin, Base):
    """Teacher profile linked to user account."""

    __tablename__ = "teacher_profiles"
    __table_args__ = (
        Index("ix_teacher_profiles_created_at", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TeacherStatusEnum] = mapped_column(
        TeacherStatusType(),
        default=TeacherStatusEnum.ACTIVE,
        nullable=False,
        index=True,
    )

    user: Mapped[User] = relationship("User", back_populates="teacher_profile")
    tags: Mapped[list[TeacherProfileTag]] = relationship(
        back_populates="teacher_profile",
        cascade="all, delete-orphan",
    )


class TeacherProfileTag(BaseModelMixin, Base):
    """Teacher profile tag used for admin filtering."""

    __tablename__ = "teacher_profile_tags"
    __table_args__ = (
        UniqueConstraint(
            "teacher_profile_id",
            "tag",
            name="uq_teacher_profile_tags_profile_tag",
        ),
    )

    teacher_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    teacher_profile: Mapped[TeacherProfile] = relationship(back_populates="tags")
