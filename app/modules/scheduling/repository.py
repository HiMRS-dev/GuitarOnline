"""Scheduling repository layer."""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RoleEnum, SlotStatusEnum
from app.modules.identity.models import Role, User
from app.modules.scheduling.models import AvailabilitySlot, TeacherWeeklyScheduleWindow
from app.modules.teachers.models import TeacherProfile


class SchedulingRepository:
    """DB access for scheduling domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_slot(
        self,
        teacher_id: UUID,
        created_by_admin_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> AvailabilitySlot:
        slot = AvailabilitySlot(
            teacher_id=teacher_id,
            created_by_admin_id=created_by_admin_id,
            start_at=start_at,
            end_at=end_at,
            status=SlotStatusEnum.OPEN,
        )
        self.session.add(slot)
        await self.session.flush()
        return slot

    async def get_slot_by_id(self, slot_id: UUID) -> AvailabilitySlot | None:
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
        return await self.session.scalar(stmt)

    async def get_slot_by_id_for_update(self, slot_id: UUID) -> AvailabilitySlot | None:
        """Load slot row with write lock for booking HOLD concurrency control."""
        stmt = select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id).with_for_update()
        return await self.session.scalar(stmt)

    async def lock_teacher_for_slot_mutation(self, teacher_id: UUID) -> None:
        """Acquire row lock for teacher to serialize slot mutations."""
        stmt = select(User.id).where(User.id == teacher_id).with_for_update()
        await self.session.execute(stmt)

    async def find_overlapping_slot(
        self,
        teacher_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> AvailabilitySlot | None:
        """Return first overlapping slot for teacher if any exists."""
        stmt = (
            select(AvailabilitySlot)
            .where(
                AvailabilitySlot.teacher_id == teacher_id,
                AvailabilitySlot.start_at < end_at,
                AvailabilitySlot.end_at > start_at,
            )
            .order_by(AvailabilitySlot.start_at.asc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def list_open_slots(
        self,
        teacher_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AvailabilitySlot], int]:
        base_stmt: Select[tuple[AvailabilitySlot]] = select(AvailabilitySlot).where(
            AvailabilitySlot.status == SlotStatusEnum.OPEN,
        )
        if teacher_id is not None:
            base_stmt = base_stmt.where(AvailabilitySlot.teacher_id == teacher_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(AvailabilitySlot.start_at.asc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def list_teacher_full_names(self, teacher_ids: list[UUID]) -> dict[UUID, str]:
        """Return best-effort teacher names keyed by user id."""
        if not teacher_ids:
            return {}

        stmt = (
            select(
                User.id,
                User.full_name,
                User.email,
                TeacherProfile.display_name,
            )
            .outerjoin(TeacherProfile, TeacherProfile.user_id == User.id)
            .where(User.id.in_(teacher_ids))
        )
        rows = (await self.session.execute(stmt)).all()
        names: dict[UUID, str] = {}
        for user_id, full_name, email, display_name in rows:
            full_name_value = str(full_name or "").strip()
            if full_name_value:
                names[user_id] = full_name_value
                continue

            display_name_value = str(display_name or "").strip()
            if display_name_value:
                names[user_id] = display_name_value
                continue

            email_value = str(email or "").strip()
            local_part = email_value.split("@", 1)[0].strip() if email_value else ""
            names[user_id] = local_part or str(user_id)

        return names

    async def set_slot_status(
        self,
        slot: AvailabilitySlot,
        status: SlotStatusEnum,
    ) -> AvailabilitySlot:
        slot.status = status
        if status != SlotStatusEnum.BLOCKED:
            slot.block_reason = None
            slot.blocked_at = None
            slot.blocked_by_admin_id = None
        await self.session.flush()
        return slot

    async def get_teacher_timezone(self, teacher_id: UUID) -> str | None:
        """Return timezone for existing teacher user."""
        teacher_role_id_subquery = (
            select(Role.id).where(Role.name == RoleEnum.TEACHER).scalar_subquery()
        )
        stmt = select(User.timezone).where(
            User.id == teacher_id,
            User.role_id == teacher_role_id_subquery,
        )
        return await self.session.scalar(stmt)

    async def list_teacher_weekly_schedule_windows(
        self,
        teacher_id: UUID,
    ) -> list[TeacherWeeklyScheduleWindow]:
        """List persistent weekly schedule windows for teacher."""
        stmt = (
            select(TeacherWeeklyScheduleWindow)
            .where(TeacherWeeklyScheduleWindow.teacher_id == teacher_id)
            .order_by(
                TeacherWeeklyScheduleWindow.weekday.asc(),
                TeacherWeeklyScheduleWindow.start_local_time.asc(),
                TeacherWeeklyScheduleWindow.end_local_time.asc(),
                TeacherWeeklyScheduleWindow.id.asc(),
            )
        )
        return list((await self.session.scalars(stmt)).all())

    async def replace_teacher_weekly_schedule_windows(
        self,
        *,
        teacher_id: UUID,
        windows: list[tuple[int, time, time]],
    ) -> list[TeacherWeeklyScheduleWindow]:
        """Replace teacher weekly schedule windows atomically."""
        await self.session.execute(
            delete(TeacherWeeklyScheduleWindow).where(
                TeacherWeeklyScheduleWindow.teacher_id == teacher_id,
            ),
        )
        created: list[TeacherWeeklyScheduleWindow] = []
        for weekday, start_local_time, end_local_time in windows:
            item = TeacherWeeklyScheduleWindow(
                teacher_id=teacher_id,
                weekday=weekday,
                start_local_time=start_local_time,
                end_local_time=end_local_time,
            )
            self.session.add(item)
            created.append(item)
        await self.session.flush()
        return sorted(
            created,
            key=lambda item: (
                item.weekday,
                item.start_local_time,
                item.end_local_time,
                str(item.id),
            ),
        )
