"""Lessons business logic layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.enums import LessonStatusEnum, RoleEnum
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.booking.repository import BookingRepository
from app.modules.identity.models import User
from app.modules.lessons.models import Lesson
from app.modules.lessons.moderation import validate_report_content
from app.modules.lessons.repository import LessonsRepository
from app.modules.lessons.schemas import LessonCreate, LessonUpdate, TeacherLessonReportRequest
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)
from app.shared.utils import ensure_utc, utc_now

settings = get_settings()


class LessonsService:
    """Lessons domain service."""

    def __init__(
        self,
        repository: LessonsRepository,
        billing_repository: BillingRepository | None = None,
        booking_repository: BookingRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self.repository = repository
        self.billing_repository = billing_repository
        self.booking_repository = booking_repository
        self.audit_repository = audit_repository

    @staticmethod
    def _normalize_links(links: list | None) -> list[str] | None:
        if links is None:
            return None
        return [str(link) for link in links]

    @staticmethod
    def _generate_meeting_url_from_template(lesson: Lesson) -> str:
        template = settings.lesson_meeting_url_template
        if template is None or not template.strip():
            raise BusinessRuleException("Meeting URL template is not configured")

        return template.format(
            lesson_id=str(lesson.id),
            booking_id=str(lesson.booking_id),
            teacher_id=str(lesson.teacher_id),
            student_id=str(lesson.student_id),
        )

    def _resolve_meeting_url_change(
        self,
        *,
        lesson: Lesson,
        meeting_url,
        use_meeting_url_template: bool,
    ) -> str:
        if meeting_url is not None and use_meeting_url_template:
            raise BusinessRuleException(
                "Provide either meeting_url or use_meeting_url_template, not both",
            )
        if use_meeting_url_template:
            return self._generate_meeting_url_from_template(lesson)
        if meeting_url is None:
            raise BusinessRuleException("meeting_url is required when template mode is disabled")
        return str(meeting_url)

    @staticmethod
    def _collect_changed_fields(lesson: Lesson, changes: dict) -> list[str]:
        fields = ("notes", "homework", "links", "meeting_url", "recording_url")
        changed: list[str] = []
        for field in fields:
            if field not in changes:
                continue
            if getattr(lesson, field) != changes[field]:
                changed.append(field)
        return changed

    async def create_lesson(self, payload: LessonCreate, actor: User) -> Lesson:
        """Create lesson entity from booking data."""
        if actor.role.name not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
            raise UnauthorizedException("Only admin or teacher can create lessons")

        existing = await self.repository.get_lesson_by_booking_id(payload.booking_id)
        if existing is not None:
            raise ConflictException("Lesson already exists for booking")

        start_at = ensure_utc(payload.scheduled_start_at)
        end_at = ensure_utc(payload.scheduled_end_at)
        if end_at <= start_at:
            from app.shared.exceptions import BusinessRuleException

            raise BusinessRuleException("Lesson end must be greater than start")

        return await self.repository.create_lesson(
            booking_id=payload.booking_id,
            student_id=payload.student_id,
            teacher_id=payload.teacher_id,
            scheduled_start_at=start_at,
            scheduled_end_at=end_at,
            topic=payload.topic,
            notes=payload.notes,
        )

    async def update_lesson(self, lesson_id, payload: LessonUpdate, actor: User) -> Lesson:
        """Update lesson details or status."""
        lesson = await self.repository.get_lesson_by_id(lesson_id)
        if lesson is None:
            raise NotFoundException("Lesson not found")

        if actor.role.name not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
            raise UnauthorizedException("Only admin or teacher can update lessons")

        if actor.role.name == RoleEnum.TEACHER and lesson.teacher_id != actor.id:
            raise UnauthorizedException("Teacher can update only own lessons")

        changes = payload.model_dump(exclude_none=True)
        if "links" in changes:
            changes["links"] = self._normalize_links(changes["links"])
        use_template = bool(changes.pop("use_meeting_url_template", False))
        if "meeting_url" in changes or use_template:
            changes["meeting_url"] = self._resolve_meeting_url_change(
                lesson=lesson,
                meeting_url=changes.get("meeting_url"),
                use_meeting_url_template=use_template,
            )
        if "recording_url" in changes:
            changes["recording_url"] = str(changes["recording_url"])

        return await self.repository.update_lesson(lesson, **changes)

    async def report_lesson(
        self,
        lesson_id: UUID,
        payload: TeacherLessonReportRequest,
        actor: User,
    ) -> Lesson:
        """Create or update teacher lesson report."""
        if actor.role.name != RoleEnum.TEACHER:
            raise UnauthorizedException("Only teacher can report lesson")

        lesson = await self.repository.get_lesson_by_id(lesson_id)
        if lesson is None:
            raise NotFoundException("Lesson not found")
        if lesson.teacher_id != actor.id:
            raise UnauthorizedException("Teacher can report only own lessons")

        changes = payload.model_dump(exclude_none=True)
        if "links" in changes:
            changes["links"] = self._normalize_links(changes.get("links"))
        validate_report_content(
            notes=changes.get("notes"),
            homework=changes.get("homework"),
            links=changes.get("links"),
        )
        use_template = bool(changes.pop("use_meeting_url_template", False))
        if "meeting_url" in changes or use_template:
            changes["meeting_url"] = self._resolve_meeting_url_change(
                lesson=lesson,
                meeting_url=changes.get("meeting_url"),
                use_meeting_url_template=use_template,
            )
        if "recording_url" in changes:
            changes["recording_url"] = str(changes["recording_url"])
        changed_fields = self._collect_changed_fields(lesson, changes)
        updated = await self.repository.update_lesson(lesson, **changes)

        if changed_fields and self.audit_repository is not None:
            await self.audit_repository.create_audit_log(
                actor_id=actor.id,
                action="lesson.report.update",
                entity_type="lesson",
                entity_id=str(updated.id),
                payload={
                    "lesson_id": str(updated.id),
                    "changed_fields": changed_fields,
                    "changed_count": len(changed_fields),
                },
            )

        return updated

    async def mark_no_show(self, lesson_id: UUID, actor: User) -> Lesson:
        """Mark lesson as NO_SHOW via admin-only operation."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can mark lesson as no-show")

        lesson = await self.repository.get_lesson_by_id(lesson_id)
        if lesson is None:
            raise NotFoundException("Lesson not found")
        if lesson.status == LessonStatusEnum.NO_SHOW:
            return lesson
        if lesson.status != LessonStatusEnum.SCHEDULED:
            raise ConflictException("Only scheduled lesson can be marked as no-show")

        return await self.repository.update_lesson(lesson, status=LessonStatusEnum.NO_SHOW)

    async def complete_lesson(self, lesson_id: UUID, actor: User) -> Lesson:
        """Mark lesson as COMPLETED and consume reserved package lesson once."""
        lesson = await self.repository.get_lesson_by_id(lesson_id)
        if lesson is None:
            raise NotFoundException("Lesson not found")

        if actor.role.name not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
            raise UnauthorizedException("Only admin or teacher can complete lessons")
        if actor.role.name == RoleEnum.TEACHER and lesson.teacher_id != actor.id:
            raise UnauthorizedException("Teacher can complete only own lessons")

        if lesson.status == LessonStatusEnum.COMPLETED:
            if lesson.consumed_at is not None:
                return lesson
            return await self.repository.update_lesson(lesson, consumed_at=utc_now())
        if lesson.status != LessonStatusEnum.SCHEDULED:
            raise ConflictException("Only scheduled lesson can be completed")

        if self.booking_repository is None or self.billing_repository is None:
            raise RuntimeError("LessonsService is not configured for completion consumption")

        booking = await self.booking_repository.get_booking_by_id(lesson.booking_id)
        if booking is None:
            raise NotFoundException("Booking not found")
        if booking.package_id is None:
            raise ConflictException("Lesson booking has no package")

        package = await self.billing_repository.get_package_by_id(booking.package_id)
        if package is None:
            raise NotFoundException("Package not found")
        if package.lessons_reserved <= 0:
            raise ConflictException("No reserved lessons to consume")
        if package.lessons_left <= 0:
            raise ConflictException("No lessons left")

        await self.billing_repository.consume_reserved_package_lesson(package)
        return await self.repository.update_lesson(
            lesson,
            status=LessonStatusEnum.COMPLETED,
            consumed_at=utc_now(),
        )

    async def list_lessons(self, actor: User, limit: int, offset: int) -> tuple[list[Lesson], int]:
        """List lessons for current student."""
        if actor.role.name != RoleEnum.STUDENT:
            raise UnauthorizedException("Only student can list own lessons")

        return await self.repository.list_lessons_for_user(
            actor.id,
            RoleEnum.STUDENT,
            limit,
            offset,
        )

    async def list_teacher_lessons(
        self,
        actor: User,
        *,
        from_utc,
        to_utc,
        limit: int,
        offset: int,
    ) -> tuple[list[Lesson], int]:
        """List teacher-owned lessons with optional UTC range filters."""
        if actor.role.name != RoleEnum.TEACHER:
            raise UnauthorizedException("Only teacher can list teacher lessons")

        normalized_from_utc = ensure_utc(from_utc) if from_utc is not None else None
        normalized_to_utc = ensure_utc(to_utc) if to_utc is not None else None
        if (
            normalized_from_utc is not None
            and normalized_to_utc is not None
            and normalized_from_utc > normalized_to_utc
        ):
            raise BusinessRuleException("from_utc must be less than or equal to to_utc")

        return await self.repository.list_teacher_lessons(
            teacher_id=actor.id,
            from_utc=normalized_from_utc,
            to_utc=normalized_to_utc,
            limit=limit,
            offset=offset,
        )


async def get_lessons_service(session: AsyncSession = Depends(get_db_session)) -> LessonsService:
    """Dependency provider for lessons service."""
    return LessonsService(
        repository=LessonsRepository(session),
        billing_repository=BillingRepository(session),
        booking_repository=BookingRepository(session),
        audit_repository=AuditRepository(session),
    )
