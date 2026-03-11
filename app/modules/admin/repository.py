"""Admin repository layer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.config import get_settings
from app.core.enums import (
    BookingStatusEnum,
    LessonStatusEnum,
    NotificationStatusEnum,
    OutboxStatusEnum,
    PackageStatusEnum,
    PaymentStatusEnum,
    RoleEnum,
    SlotStatusEnum,
    TeacherStatusEnum,
)
from app.modules.admin.models import AdminAction
from app.modules.audit.models import AuditLog, OutboxEvent
from app.modules.billing.models import LessonPackage, Payment
from app.modules.booking.models import Booking
from app.modules.identity.models import Role, User
from app.modules.lessons.models import Lesson
from app.modules.notifications.models import Notification
from app.modules.scheduling.models import AvailabilitySlot
from app.modules.teachers.models import TeacherProfile, TeacherProfileTag
from app.shared.utils import utc_now

ACTIVE_BOOKING_STATUSES: tuple[BookingStatusEnum, ...] = (
    BookingStatusEnum.HOLD,
    BookingStatusEnum.CONFIRMED,
)
settings = get_settings()


class AdminRepository:
    """DB operations for admin domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _non_synthetic_email_filters(email_column: object) -> list[object]:
        filters: list[object] = []
        for prefix in settings.kpi_excluded_email_prefixes:
            normalized = prefix.strip().lower()
            if not normalized:
                continue
            filters.append(func.lower(email_column).notlike(f"{normalized}%"))
        return filters

    async def create_action(
        self,
        admin_id: UUID,
        action: str,
        target_type: str,
        target_id: str | None,
        payload: dict,
    ) -> AdminAction:
        action_obj = AdminAction(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )
        self.session.add(action_obj)
        await self.session.flush()
        return action_obj

    async def get_role_by_name(self, role_name: RoleEnum) -> Role | None:
        """Resolve role row by enum name."""
        stmt = select(Role).where(Role.name == role_name)
        return await self.session.scalar(stmt)

    async def get_user_by_email(self, email: str) -> User | None:
        """Return user by email with role/profile relationships preloaded."""
        stmt = (
            select(User)
            .where(User.email == email)
            .options(
                selectinload(User.role),
                selectinload(User.teacher_profile),
            )
        )
        return await self.session.scalar(stmt)

    async def create_provisioned_user(
        self,
        *,
        email: str,
        password_hash: str,
        timezone: str,
        role_id: UUID,
        role_name: RoleEnum,
        teacher_profile: dict[str, object] | None,
        admin_id: UUID,
    ) -> User:
        """Create privileged user and optional teacher profile with audit trail."""
        user = User(
            email=email,
            password_hash=password_hash,
            timezone=timezone,
            role_id=role_id,
        )
        self.session.add(user)
        await self.session.flush()

        profile: TeacherProfile | None = None
        if role_name == RoleEnum.TEACHER:
            profile_payload = teacher_profile or {}
            profile = TeacherProfile(
                user_id=user.id,
                display_name=str(profile_payload.get("display_name", "")),
                bio=str(profile_payload.get("bio", "")),
                experience_years=int(profile_payload.get("experience_years", 0)),
                status=TeacherStatusEnum.PENDING,
                is_approved=False,
            )
            self.session.add(profile)
            await self.session.flush()

        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.user.provision",
                entity_type="user",
                entity_id=str(user.id),
                payload={
                    "email": user.email,
                    "role": str(role_name),
                    "teacher_profile_id": str(profile.id) if profile is not None else None,
                    "teacher_profile_created": profile is not None,
                },
            ),
        )
        await self.session.flush()

        stmt = (
            select(User)
            .where(User.id == user.id)
            .options(
                selectinload(User.role),
                selectinload(User.teacher_profile),
            )
        )
        created_user = await self.session.scalar(stmt)
        if created_user is None:
            return user
        return created_user

    async def list_users(
        self,
        *,
        limit: int,
        offset: int,
        role: RoleEnum | None,
        is_active: bool | None,
        q: str | None,
    ) -> tuple[list[dict[str, object]], int]:
        """List users for admin user-management views."""
        normalized_q = q.strip() if q else None

        base_stmt: Select[tuple[UUID]] = select(User.id).join(Role, Role.id == User.role_id)
        if role is not None:
            base_stmt = base_stmt.where(Role.name == role)
        if is_active is not None:
            base_stmt = base_stmt.where(User.is_active.is_(is_active))
        if normalized_q:
            pattern = f"%{normalized_q}%"
            base_stmt = base_stmt.outerjoin(
                TeacherProfile,
                TeacherProfile.user_id == User.id,
            ).where(
                or_(
                    User.email.ilike(pattern),
                    TeacherProfile.display_name.ilike(pattern),
                ),
            )

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(total_stmt)) or 0)

        paged_ids_stmt = (
            base_stmt.order_by(User.created_at.desc(), User.id.desc()).limit(limit).offset(offset)
        )
        user_ids = list((await self.session.scalars(paged_ids_stmt)).all())
        if not user_ids:
            return [], total

        users_stmt = (
            select(User)
            .where(User.id.in_(user_ids))
            .options(
                selectinload(User.role),
                selectinload(User.teacher_profile),
            )
        )
        users = (await self.session.scalars(users_stmt)).all()
        user_by_id = {user.id: user for user in users}

        items: list[dict[str, object]] = []
        for user_id in user_ids:
            user = user_by_id.get(user_id)
            if user is None or user.role is None:
                continue
            items.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "timezone": user.timezone,
                    "role": user.role.name,
                    "is_active": user.is_active,
                    "teacher_profile_display_name": (
                        user.teacher_profile.display_name
                        if user.teacher_profile is not None
                        else None
                    ),
                    "created_at_utc": user.created_at,
                    "updated_at_utc": user.updated_at,
                },
            )

        return items, total

    async def get_user_by_id(self, *, user_id: UUID, lock_for_update: bool = False) -> User | None:
        """Get user by id with role/profile relationships preloaded."""
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.role),
                selectinload(User.teacher_profile),
            )
        )
        if lock_for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def set_user_active(
        self,
        *,
        user: User,
        is_active: bool,
        admin_id: UUID,
    ) -> User:
        """Update user active flag and persist audit log."""
        previous_is_active = user.is_active
        user.is_active = is_active

        action = "admin.user.activate" if is_active else "admin.user.deactivate"
        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action=action,
                entity_type="user",
                entity_id=str(user.id),
                payload={
                    "email": user.email,
                    "role": str(user.role.name) if user.role is not None else None,
                    "from_is_active": previous_is_active,
                    "to_is_active": user.is_active,
                },
            ),
        )
        await self.session.flush()
        return user

    async def list_actions(self, limit: int, offset: int) -> tuple[list[AdminAction], int]:
        base_stmt: Select[tuple[AdminAction]] = select(AdminAction)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(AdminAction.created_at.desc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def list_teachers(
        self,
        *,
        limit: int,
        offset: int,
        status: TeacherStatusEnum | None,
        verified: bool | None,
        q: str | None,
        tag: str | None,
    ) -> tuple[list[dict[str, object]], int]:
        """List teachers for admin scheduling and moderation flows."""
        normalized_q = q.strip() if q else None
        normalized_tag = tag.strip().lower() if tag else None
        teacher_role_id_subquery = (
            select(Role.id).where(Role.name == RoleEnum.TEACHER).scalar_subquery()
        )

        base_stmt: Select[tuple[UUID]] = (
            select(TeacherProfile.id)
            .join(User, User.id == TeacherProfile.user_id)
            .where(User.role_id == teacher_role_id_subquery)
        )

        if status is not None:
            base_stmt = base_stmt.where(TeacherProfile.status == status)
        if verified is not None:
            base_stmt = base_stmt.where(TeacherProfile.is_approved.is_(verified))
        if normalized_q:
            pattern = f"%{normalized_q}%"
            base_stmt = base_stmt.where(
                or_(
                    TeacherProfile.display_name.ilike(pattern),
                    User.email.ilike(pattern),
                ),
            )
        if normalized_tag:
            tag_exists = (
                select(TeacherProfileTag.id)
                .where(
                    TeacherProfileTag.teacher_profile_id == TeacherProfile.id,
                    func.lower(TeacherProfileTag.tag) == normalized_tag,
                )
                .exists()
            )
            base_stmt = base_stmt.where(tag_exists)

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(total_stmt)) or 0)

        paged_ids_stmt = (
            base_stmt.order_by(TeacherProfile.created_at.desc(), TeacherProfile.id.desc())
            .limit(limit)
            .offset(offset)
        )
        teacher_profile_ids = list((await self.session.scalars(paged_ids_stmt)).all())
        if not teacher_profile_ids:
            return [], total

        profiles_stmt = (
            select(TeacherProfile)
            .where(TeacherProfile.id.in_(teacher_profile_ids))
            .options(
                selectinload(TeacherProfile.user),
                selectinload(TeacherProfile.tags),
            )
        )
        profiles = (await self.session.scalars(profiles_stmt)).all()
        profile_by_id = {profile.id: profile for profile in profiles}

        items: list[dict[str, object]] = []
        for profile_id in teacher_profile_ids:
            profile = profile_by_id.get(profile_id)
            if profile is None:
                continue

            serialized = self._serialize_teacher_profile(profile)
            if serialized is None:
                continue
            items.append(serialized)

        return items, total

    async def get_teacher_detail(self, *, teacher_id: UUID) -> dict[str, object] | None:
        """Get teacher detail by teacher user id."""
        profile = await self._get_teacher_profile_by_user_id(teacher_id=teacher_id)
        if profile is None:
            return None

        return self._serialize_teacher_profile(profile, include_profile_fields=True)

    async def verify_teacher(
        self,
        *,
        teacher_id: UUID,
        admin_id: UUID,
    ) -> dict[str, object] | None:
        """Verify teacher profile and write audit trail."""
        profile = await self._get_teacher_profile_by_user_id(
            teacher_id=teacher_id,
            lock_for_update=True,
        )
        if profile is None:
            return None

        user = profile.user
        if user is None:
            return None

        previous_status = profile.status
        previous_is_approved = profile.is_approved

        profile.status = TeacherStatusEnum.VERIFIED
        profile.is_approved = True

        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.teacher.verify",
                entity_type="teacher_profile",
                entity_id=str(profile.id),
                payload={
                    "teacher_id": str(profile.user_id),
                    "from_status": str(previous_status),
                    "to_status": str(profile.status),
                    "from_is_approved": previous_is_approved,
                    "to_is_approved": profile.is_approved,
                    "user_is_active": user.is_active,
                },
            ),
        )
        await self.session.flush()
        return self._serialize_teacher_profile(profile, include_profile_fields=True)

    async def disable_teacher(
        self,
        *,
        teacher_id: UUID,
        admin_id: UUID,
    ) -> dict[str, object] | None:
        """Disable teacher profile and user account and write audit trail."""
        profile = await self._get_teacher_profile_by_user_id(
            teacher_id=teacher_id,
            lock_for_update=True,
        )
        if profile is None:
            return None

        user = profile.user
        if user is None:
            return None

        previous_status = profile.status
        previous_is_approved = profile.is_approved
        previous_is_active = user.is_active

        profile.status = TeacherStatusEnum.DISABLED
        profile.is_approved = False
        user.is_active = False

        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.teacher.disable",
                entity_type="teacher_profile",
                entity_id=str(profile.id),
                payload={
                    "teacher_id": str(profile.user_id),
                    "from_status": str(previous_status),
                    "to_status": str(profile.status),
                    "from_is_approved": previous_is_approved,
                    "to_is_approved": profile.is_approved,
                    "from_user_is_active": previous_is_active,
                    "to_user_is_active": user.is_active,
                },
            ),
        )
        await self.session.flush()
        return self._serialize_teacher_profile(profile, include_profile_fields=True)

    async def _get_teacher_profile_by_user_id(
        self,
        *,
        teacher_id: UUID,
        lock_for_update: bool = False,
    ) -> TeacherProfile | None:
        stmt = (
            select(TeacherProfile)
            .join(User, User.id == TeacherProfile.user_id)
            .join(Role, Role.id == User.role_id)
            .where(
                TeacherProfile.user_id == teacher_id,
                Role.name == RoleEnum.TEACHER,
            )
            .options(
                selectinload(TeacherProfile.user),
                selectinload(TeacherProfile.tags),
            )
        )
        if lock_for_update:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    def _serialize_teacher_profile(
        self,
        profile: TeacherProfile,
        *,
        include_profile_fields: bool = False,
    ) -> dict[str, object] | None:
        user = profile.user
        if user is None:
            return None

        tags = sorted({tag_row.tag for tag_row in profile.tags}, key=str.lower)
        data: dict[str, object] = {
            "teacher_id": profile.user_id,
            "profile_id": profile.id,
            "email": user.email,
            "display_name": profile.display_name,
            "status": profile.status,
            "verified": profile.is_approved,
            "is_active": user.is_active,
            "tags": tags,
            "created_at_utc": profile.created_at,
            "updated_at_utc": profile.updated_at,
        }
        if include_profile_fields:
            data["bio"] = profile.bio
            data["experience_years"] = profile.experience_years
        return data

    async def list_slots(
        self,
        *,
        teacher_id: UUID | None,
        from_utc: datetime | None,
        to_utc: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List slots with booking relation snapshot for admin views."""
        base_stmt: Select[tuple[AvailabilitySlot, UUID | None, BookingStatusEnum | None]] = (
            select(
                AvailabilitySlot,
                Booking.id.label("booking_id"),
                Booking.status.label("booking_status"),
            ).outerjoin(
                Booking,
                and_(
                    Booking.slot_id == AvailabilitySlot.id,
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                ),
            )
        )

        if teacher_id is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.teacher_id == teacher_id)
        if from_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at >= from_utc)
        if to_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at <= to_utc)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(AvailabilitySlot.start_at.asc()).limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).all()

        items: list[dict[str, object]] = []
        for slot, booking_id, booking_status in rows:
            items.append(
                {
                    "slot_id": slot.id,
                    "teacher_id": slot.teacher_id,
                    "created_by_admin_id": slot.created_by_admin_id,
                    "start_at_utc": slot.start_at,
                    "end_at_utc": slot.end_at,
                    "slot_status": slot.status,
                    "booking_id": booking_id,
                    "booking_status": booking_status,
                    "created_at_utc": slot.created_at,
                    "updated_at_utc": slot.updated_at,
                },
            )
        return items, total

    async def list_bookings(
        self,
        *,
        teacher_id: UUID | None,
        student_id: UUID | None,
        status: BookingStatusEnum | None,
        from_utc: datetime | None,
        to_utc: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List bookings with admin filters and slot-time range constraints."""
        base_stmt: Select[tuple[Booking, datetime, datetime]] = (
            select(
                Booking,
                AvailabilitySlot.start_at.label("slot_start_at_utc"),
                AvailabilitySlot.end_at.label("slot_end_at_utc"),
            ).join(
                AvailabilitySlot,
                AvailabilitySlot.id == Booking.slot_id,
            )
        )

        if teacher_id is not None:
            base_stmt = base_stmt.where(Booking.teacher_id == teacher_id)
        if student_id is not None:
            base_stmt = base_stmt.where(Booking.student_id == student_id)
        if status is not None:
            base_stmt = base_stmt.where(Booking.status == status)
        if from_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at >= from_utc)
        if to_utc is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.start_at <= to_utc)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = (
            base_stmt.order_by(AvailabilitySlot.start_at.asc(), Booking.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()

        items: list[dict[str, object]] = []
        for booking, slot_start_at_utc, slot_end_at_utc in rows:
            items.append(
                {
                    "booking_id": booking.id,
                    "slot_id": booking.slot_id,
                    "student_id": booking.student_id,
                    "teacher_id": booking.teacher_id,
                    "package_id": booking.package_id,
                    "status": booking.status,
                    "slot_start_at_utc": slot_start_at_utc,
                    "slot_end_at_utc": slot_end_at_utc,
                    "hold_expires_at_utc": booking.hold_expires_at,
                    "confirmed_at_utc": booking.confirmed_at,
                    "canceled_at_utc": booking.canceled_at,
                    "cancellation_reason": booking.cancellation_reason,
                    "refund_returned": booking.refund_returned,
                    "rescheduled_from_booking_id": booking.rescheduled_from_booking_id,
                    "created_at_utc": booking.created_at,
                    "updated_at_utc": booking.updated_at,
                },
            )
        return items, total

    async def list_packages(
        self,
        *,
        student_id: UUID | None,
        status: PackageStatusEnum | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List lesson packages for admin filters."""
        base_stmt: Select[tuple[LessonPackage]] = select(LessonPackage)
        if student_id is not None:
            base_stmt = base_stmt.where(LessonPackage.student_id == student_id)
        if status is not None:
            base_stmt = base_stmt.where(LessonPackage.status == status)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(LessonPackage.created_at.desc()).limit(limit).offset(offset)
        rows = (await self.session.scalars(stmt)).all()

        items: list[dict[str, object]] = []
        for package in rows:
            items.append(
                {
                    "package_id": package.id,
                    "student_id": package.student_id,
                    "lessons_total": package.lessons_total,
                    "lessons_left": package.lessons_left,
                    "lessons_reserved": package.lessons_reserved,
                    "price_amount": package.price_amount,
                    "price_currency": package.price_currency,
                    "expires_at_utc": package.expires_at,
                    "status": package.status,
                    "created_at_utc": package.created_at,
                    "updated_at_utc": package.updated_at,
                },
            )
        return items, total

    async def list_notifications(
        self,
        *,
        recipient_user_id: UUID | None,
        channel: str | None,
        status: NotificationStatusEnum | None,
        template_key: str | None,
        created_from_utc: datetime | None,
        created_to_utc: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List notification journal records with admin filters."""
        base_stmt: Select[tuple[Notification]] = select(Notification)
        if recipient_user_id is not None:
            base_stmt = base_stmt.where(Notification.user_id == recipient_user_id)
        if channel is not None:
            base_stmt = base_stmt.where(Notification.channel == channel)
        if status is not None:
            base_stmt = base_stmt.where(Notification.status == status)
        if template_key is not None:
            base_stmt = base_stmt.where(Notification.template_key == template_key)
        if created_from_utc is not None:
            base_stmt = base_stmt.where(Notification.created_at >= created_from_utc)
        if created_to_utc is not None:
            base_stmt = base_stmt.where(Notification.created_at <= created_to_utc)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        rows = (await self.session.scalars(stmt)).all()

        items: list[dict[str, object]] = []
        for notification in rows:
            items.append(
                {
                    "notification_id": notification.id,
                    "recipient_user_id": notification.user_id,
                    "channel": notification.channel,
                    "template_key": notification.template_key,
                    "title": notification.title,
                    "body": notification.body,
                    "status": notification.status,
                    "sent_at_utc": notification.sent_at,
                    "created_at_utc": notification.created_at,
                    "updated_at_utc": notification.updated_at,
                },
            )
        return items, total

    async def get_slot_by_id(self, slot_id: UUID) -> AvailabilitySlot | None:
        """Get slot by id for admin operations."""
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
        return await self.session.scalar(stmt)

    async def slot_has_bookings(self, slot_id: UUID) -> bool:
        """Return True if slot has at least one related booking row."""
        stmt = select(func.count(Booking.id)).where(Booking.slot_id == slot_id)
        return int((await self.session.scalar(stmt)) or 0) > 0

    async def delete_slot(self, *, slot: AvailabilitySlot, admin_id: UUID) -> None:
        """Delete slot and write audit log entry."""
        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.slot.delete",
                entity_type="availability_slot",
                entity_id=str(slot.id),
                payload={
                    "teacher_id": str(slot.teacher_id),
                    "start_at_utc": slot.start_at.isoformat(),
                    "end_at_utc": slot.end_at.isoformat(),
                    "status": str(slot.status),
                },
            ),
        )
        await self.session.delete(slot)
        await self.session.flush()

    async def block_slot(
        self,
        *,
        slot: AvailabilitySlot,
        reason: str,
        admin_id: UUID,
        blocked_at: datetime,
    ) -> AvailabilitySlot:
        """Mark slot as blocked and persist block metadata + audit."""
        previous_status = slot.status
        slot.status = SlotStatusEnum.BLOCKED
        slot.block_reason = reason
        slot.blocked_at = blocked_at
        slot.blocked_by_admin_id = admin_id

        self.session.add(
            AuditLog(
                actor_id=admin_id,
                action="admin.slot.block",
                entity_type="availability_slot",
                entity_id=str(slot.id),
                payload={
                    "teacher_id": str(slot.teacher_id),
                    "from_status": str(previous_status),
                    "to_status": str(slot.status),
                    "reason": reason,
                    "blocked_at_utc": blocked_at.isoformat(),
                },
            ),
        )
        await self.session.flush()
        return slot

    async def list_slot_status_snapshots(
        self,
        *,
        from_utc: datetime | None,
        to_utc: datetime | None,
    ) -> list[dict[str, object]]:
        """Return slot/booking/lesson status snapshots for stats aggregation."""
        stmt = (
            select(
                AvailabilitySlot.id.label("slot_id"),
                AvailabilitySlot.status.label("slot_status"),
                Booking.status.label("booking_status"),
                Lesson.status.label("lesson_status"),
            )
            .outerjoin(
                Booking,
                and_(
                    Booking.slot_id == AvailabilitySlot.id,
                    Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                ),
            )
            .outerjoin(Lesson, Lesson.booking_id == Booking.id)
        )
        if from_utc is not None:
            stmt = stmt.where(AvailabilitySlot.start_at >= from_utc)
        if to_utc is not None:
            stmt = stmt.where(AvailabilitySlot.start_at <= to_utc)

        rows = (await self.session.execute(stmt)).all()
        items: list[dict[str, object]] = []
        for row in rows:
            items.append(
                {
                    "slot_id": row.slot_id,
                    "slot_status": row.slot_status,
                    "booking_status": row.booking_status,
                    "lesson_status": row.lesson_status,
                },
            )
        return items

    async def get_kpi_overview(self) -> dict[str, datetime | int | Decimal]:
        role_counts = await self._count_users_by_role()
        booking_counts = await self._count_bookings_by_status()
        lesson_counts = await self._count_lessons_by_status()
        payment_snapshot = await self._get_payments_overview_snapshot()
        package_counts = await self._count_packages_by_status()

        users_students = role_counts.get(RoleEnum.STUDENT, 0)
        users_teachers = role_counts.get(RoleEnum.TEACHER, 0)
        users_admins = role_counts.get(RoleEnum.ADMIN, 0)

        bookings_hold = booking_counts.get(BookingStatusEnum.HOLD, 0)
        bookings_confirmed = booking_counts.get(BookingStatusEnum.CONFIRMED, 0)
        bookings_canceled = booking_counts.get(BookingStatusEnum.CANCELED, 0)
        bookings_expired = booking_counts.get(BookingStatusEnum.EXPIRED, 0)

        lessons_scheduled = lesson_counts.get(LessonStatusEnum.SCHEDULED, 0)
        lessons_completed = lesson_counts.get(LessonStatusEnum.COMPLETED, 0) + lesson_counts.get(
            LessonStatusEnum.NO_SHOW,
            0,
        )
        lessons_canceled = lesson_counts.get(LessonStatusEnum.CANCELED, 0)

        payments_pending = int(payment_snapshot["pending"])
        payments_succeeded = int(payment_snapshot["succeeded"])
        payments_failed = int(payment_snapshot["failed"])
        payments_refunded = int(payment_snapshot["refunded"])
        payments_succeeded_amount = Decimal(payment_snapshot["succeeded_amount"])
        payments_refunded_amount = Decimal(payment_snapshot["refunded_amount"])

        packages_active = package_counts.get(PackageStatusEnum.ACTIVE, 0)
        packages_expired = package_counts.get(PackageStatusEnum.EXPIRED, 0)
        packages_depleted = package_counts.get(PackageStatusEnum.DEPLETED, 0)
        packages_canceled = package_counts.get(PackageStatusEnum.CANCELED, 0)

        return {
            "generated_at": utc_now(),
            "users_total": users_students + users_teachers + users_admins,
            "users_students": users_students,
            "users_teachers": users_teachers,
            "users_admins": users_admins,
            "bookings_total": (
                bookings_hold + bookings_confirmed + bookings_canceled + bookings_expired
            ),
            "bookings_hold": bookings_hold,
            "bookings_confirmed": bookings_confirmed,
            "bookings_canceled": bookings_canceled,
            "bookings_expired": bookings_expired,
            "lessons_total": lessons_scheduled + lessons_completed + lessons_canceled,
            "lessons_scheduled": lessons_scheduled,
            "lessons_completed": lessons_completed,
            "lessons_canceled": lessons_canceled,
            "payments_total": (
                payments_pending + payments_succeeded + payments_failed + payments_refunded
            ),
            "payments_pending": payments_pending,
            "payments_succeeded": payments_succeeded,
            "payments_failed": payments_failed,
            "payments_refunded": payments_refunded,
            "payments_succeeded_amount": payments_succeeded_amount,
            "payments_refunded_amount": payments_refunded_amount,
            "payments_net_amount": payments_succeeded_amount - payments_refunded_amount,
            "packages_total": (
                packages_active + packages_expired + packages_depleted + packages_canceled
            ),
            "packages_active": packages_active,
            "packages_expired": packages_expired,
            "packages_depleted": packages_depleted,
            "packages_canceled": packages_canceled,
        }

    async def get_kpi_sales(
        self,
        *,
        from_utc: datetime,
        to_utc: datetime,
        generated_at: datetime | None = None,
    ) -> dict[str, datetime | int | Decimal]:
        payments_window_filter = (
            Payment.created_at >= from_utc,
            Payment.created_at <= to_utc,
        )
        packages_window_filter = (
            LessonPackage.created_at >= from_utc,
            LessonPackage.created_at <= to_utc,
        )
        non_synthetic_package_owner_filter = self._non_synthetic_email_filters(User.email)

        payments_aggregate_stmt = select(
            func.count(Payment.id)
            .filter(Payment.status == PaymentStatusEnum.SUCCEEDED)
            .label("payments_succeeded_count"),
            func.count(Payment.id)
            .filter(Payment.status == PaymentStatusEnum.REFUNDED)
            .label("payments_refunded_count"),
            func.coalesce(
                func.sum(Payment.amount).filter(Payment.status == PaymentStatusEnum.SUCCEEDED),
                0,
            ).label("payments_succeeded_amount"),
            func.coalesce(
                func.sum(Payment.amount).filter(Payment.status == PaymentStatusEnum.REFUNDED),
                0,
            ).label("payments_refunded_amount"),
        ).select_from(Payment).join(LessonPackage, LessonPackage.id == Payment.package_id).join(
            User,
            User.id == LessonPackage.student_id,
        ).where(*payments_window_filter, *non_synthetic_package_owner_filter)
        payments_aggregate = (await self.session.execute(payments_aggregate_stmt)).one()

        payments_succeeded_count = int(payments_aggregate.payments_succeeded_count or 0)
        payments_refunded_count = int(payments_aggregate.payments_refunded_count or 0)
        payments_succeeded_amount = Decimal(payments_aggregate.payments_succeeded_amount or 0)
        payments_refunded_amount = Decimal(payments_aggregate.payments_refunded_amount or 0)
        payments_net_amount = payments_succeeded_amount - payments_refunded_amount

        packages_created_total = int(
            (
                await self.session.scalar(
                    select(func.count(LessonPackage.id))
                    .select_from(LessonPackage)
                    .join(User, User.id == LessonPackage.student_id)
                    .where(*packages_window_filter, *non_synthetic_package_owner_filter),
                )
            )
            or 0,
        )
        packages_created_paid = int(
            (
                await self.session.scalar(
                    select(func.count(func.distinct(LessonPackage.id)))
                    .select_from(LessonPackage)
                    .join(User, User.id == LessonPackage.student_id)
                    .join(Payment, Payment.package_id == LessonPackage.id)
                    .where(
                        Payment.status == PaymentStatusEnum.SUCCEEDED,
                        *packages_window_filter,
                        *payments_window_filter,
                        *non_synthetic_package_owner_filter,
                    ),
                )
            )
            or 0,
        )
        packages_created_unpaid = max(packages_created_total - packages_created_paid, 0)
        packages_created_paid_conversion_rate = (
            Decimal(packages_created_paid) / Decimal(packages_created_total)
            if packages_created_total > 0
            else Decimal("0")
        )

        return {
            "generated_at": generated_at or utc_now(),
            "from_utc": from_utc,
            "to_utc": to_utc,
            "payments_succeeded_count": payments_succeeded_count,
            "payments_refunded_count": payments_refunded_count,
            "payments_succeeded_amount": payments_succeeded_amount,
            "payments_refunded_amount": payments_refunded_amount,
            "payments_net_amount": payments_net_amount,
            "packages_created_total": packages_created_total,
            "packages_created_paid": packages_created_paid,
            "packages_created_unpaid": packages_created_unpaid,
            "packages_created_paid_conversion_rate": packages_created_paid_conversion_rate,
        }

    async def _count_users_by_role(self) -> dict[RoleEnum, int]:
        stmt = (
            select(Role.name, func.count(User.id))
            .join(User, User.role_id == Role.id)
            .where(*self._non_synthetic_email_filters(User.email))
            .group_by(Role.name)
        )
        rows = (await self.session.execute(stmt)).all()
        return {role_name: int(count) for role_name, count in rows}

    async def _count_bookings_by_status(self) -> dict[BookingStatusEnum, int]:
        student_user = aliased(User)
        teacher_user = aliased(User)
        stmt = (
            select(Booking.status, func.count(Booking.id))
            .join(student_user, student_user.id == Booking.student_id)
            .join(teacher_user, teacher_user.id == Booking.teacher_id)
            .where(*self._non_synthetic_email_filters(student_user.email))
            .where(*self._non_synthetic_email_filters(teacher_user.email))
            .group_by(Booking.status)
        )
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _count_lessons_by_status(self) -> dict[LessonStatusEnum, int]:
        student_user = aliased(User)
        teacher_user = aliased(User)
        stmt = (
            select(Lesson.status, func.count(Lesson.id))
            .join(student_user, student_user.id == Lesson.student_id)
            .join(teacher_user, teacher_user.id == Lesson.teacher_id)
            .where(*self._non_synthetic_email_filters(student_user.email))
            .where(*self._non_synthetic_email_filters(teacher_user.email))
            .group_by(Lesson.status)
        )
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _count_payments_by_status(self) -> dict[PaymentStatusEnum, int]:
        stmt = (
            select(Payment.status, func.count(Payment.id))
            .select_from(Payment)
            .join(LessonPackage, LessonPackage.id == Payment.package_id)
            .join(User, User.id == LessonPackage.student_id)
            .where(*self._non_synthetic_email_filters(User.email))
            .group_by(Payment.status)
        )
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _count_packages_by_status(self) -> dict[PackageStatusEnum, int]:
        stmt = (
            select(LessonPackage.status, func.count(LessonPackage.id))
            .join(User, User.id == LessonPackage.student_id)
            .where(*self._non_synthetic_email_filters(User.email))
            .group_by(LessonPackage.status)
        )
        rows = (await self.session.execute(stmt)).all()
        return {status: int(count) for status, count in rows}

    async def _sum_payments_by_status(self, status: PaymentStatusEnum) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(Payment.amount), 0))
            .select_from(Payment)
            .join(LessonPackage, LessonPackage.id == Payment.package_id)
            .join(User, User.id == LessonPackage.student_id)
            .where(Payment.status == status, *self._non_synthetic_email_filters(User.email))
        )
        value = (await self.session.scalar(stmt)) or Decimal("0")
        return Decimal(value)

    async def _get_payments_overview_snapshot(self) -> dict[str, int | Decimal]:
        stmt = select(
            func.count(Payment.id)
            .filter(Payment.status == PaymentStatusEnum.PENDING)
            .label("pending"),
            func.count(Payment.id)
            .filter(Payment.status == PaymentStatusEnum.SUCCEEDED)
            .label("succeeded"),
            func.count(Payment.id)
            .filter(Payment.status == PaymentStatusEnum.FAILED)
            .label("failed"),
            func.count(Payment.id)
            .filter(Payment.status == PaymentStatusEnum.REFUNDED)
            .label("refunded"),
            func.coalesce(
                func.sum(Payment.amount).filter(Payment.status == PaymentStatusEnum.SUCCEEDED),
                0,
            ).label("succeeded_amount"),
            func.coalesce(
                func.sum(Payment.amount).filter(Payment.status == PaymentStatusEnum.REFUNDED),
                0,
            ).label("refunded_amount"),
        ).select_from(Payment).join(LessonPackage, LessonPackage.id == Payment.package_id).join(
            User,
            User.id == LessonPackage.student_id,
        ).where(*self._non_synthetic_email_filters(User.email))
        row = (await self.session.execute(stmt)).one()
        return {
            "pending": int(row.pending or 0),
            "succeeded": int(row.succeeded or 0),
            "failed": int(row.failed or 0),
            "refunded": int(row.refunded or 0),
            "succeeded_amount": Decimal(row.succeeded_amount or 0),
            "refunded_amount": Decimal(row.refunded_amount or 0),
        }

    async def get_operations_overview(
        self,
        *,
        max_retries: int,
        now: datetime | None = None,
    ) -> dict[str, datetime | int]:
        snapshot_now = now or utc_now()

        outbox_pending = await self._count_outbox_by_status(OutboxStatusEnum.PENDING)
        outbox_failed_retryable = await self._count_failed_outbox(
            retryable=True,
            max_retries=max_retries,
        )
        outbox_failed_dead_letter = await self._count_failed_outbox(
            retryable=False,
            max_retries=max_retries,
        )
        notifications_failed = await self._count_notifications_by_status(
            NotificationStatusEnum.FAILED,
        )
        stale_booking_holds = await self._count_stale_booking_holds(snapshot_now)
        overdue_active_packages = await self._count_overdue_active_packages(snapshot_now)

        return {
            "generated_at": snapshot_now,
            "max_retries": max_retries,
            "outbox_pending": outbox_pending,
            "outbox_failed_retryable": outbox_failed_retryable,
            "outbox_failed_dead_letter": outbox_failed_dead_letter,
            "notifications_failed": notifications_failed,
            "stale_booking_holds": stale_booking_holds,
            "overdue_active_packages": overdue_active_packages,
        }

    async def _count_outbox_by_status(self, status: OutboxStatusEnum) -> int:
        stmt = select(func.count(OutboxEvent.id)).where(OutboxEvent.status == status)
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_failed_outbox(self, *, retryable: bool, max_retries: int) -> int:
        comparison = (
            OutboxEvent.retries < max_retries
            if retryable
            else OutboxEvent.retries >= max_retries
        )
        stmt = select(func.count(OutboxEvent.id)).where(
            OutboxEvent.status == OutboxStatusEnum.FAILED,
            comparison,
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_notifications_by_status(self, status: NotificationStatusEnum) -> int:
        stmt = select(func.count(Notification.id)).where(Notification.status == status)
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_stale_booking_holds(self, now: datetime) -> int:
        stmt = select(func.count(Booking.id)).where(
            Booking.status == BookingStatusEnum.HOLD,
            Booking.hold_expires_at.is_not(None),
            Booking.hold_expires_at <= now,
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def _count_overdue_active_packages(self, now: datetime) -> int:
        stmt = select(func.count(LessonPackage.id)).where(
            LessonPackage.status == PackageStatusEnum.ACTIVE,
            LessonPackage.expires_at <= now,
        )
        return int((await self.session.scalar(stmt)) or 0)
