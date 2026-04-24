"""Scheduling business logic layer."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.enums import RoleEnum, SlotStatusEnum
from app.modules.audit.repository import AuditRepository
from app.modules.identity.models import User
from app.modules.scheduling.models import AvailabilitySlot, TeacherWeeklyScheduleWindow
from app.modules.scheduling.repository import SchedulingRepository
from app.modules.scheduling.schemas import SlotCreate
from app.shared.exceptions import BusinessRuleException, NotFoundException, UnauthorizedException
from app.shared.utils import ensure_utc, utc_now

settings = get_settings()
MOSCOW_TIMEZONE = "Europe/Moscow"
AUTO_SLOT_HORIZON_DAYS = 21


class SchedulingService:
    """Scheduling domain service."""

    def __init__(
        self,
        repository: SchedulingRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.repository = repository
        self.audit_repository = audit_repository

    async def create_slot(self, payload: SlotCreate, actor: User) -> AvailabilitySlot:
        """Create teacher availability slot (admin only)."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create slots")

        start_at = ensure_utc(payload.start_at)
        end_at = ensure_utc(payload.end_at)

        if end_at <= start_at:
            raise BusinessRuleException("Slot end_at must be after start_at")
        if start_at <= utc_now():
            raise BusinessRuleException("Slot start_at must be in the future")
        duration_minutes = int((end_at - start_at).total_seconds() // 60)
        if duration_minutes < settings.slot_min_duration_minutes:
            raise BusinessRuleException(
                f"Slot duration must be at least {settings.slot_min_duration_minutes} minutes",
            )

        await self.repository.lock_teacher_for_slot_mutation(payload.teacher_id)
        overlapping_slot = await self.repository.find_overlapping_slot(
            teacher_id=payload.teacher_id,
            start_at=start_at,
            end_at=end_at,
        )
        if overlapping_slot is not None:
            raise BusinessRuleException(
                "Slot overlaps with an existing slot for this teacher",
                details={
                    "overlap_slot_id": str(overlapping_slot.id),
                    "overlap_start_at_utc": overlapping_slot.start_at.isoformat(),
                    "overlap_end_at_utc": overlapping_slot.end_at.isoformat(),
                },
            )

        slot = await self.repository.create_slot(payload.teacher_id, actor.id, start_at, end_at)
        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="admin.slot.create",
            entity_type="availability_slot",
            entity_id=str(slot.id),
            payload={
                "teacher_id": str(slot.teacher_id),
                "start_at_utc": slot.start_at.isoformat(),
                "end_at_utc": slot.end_at.isoformat(),
            },
        )
        return slot

    async def get_teacher_weekly_schedule(
        self,
        *,
        teacher_id: UUID,
        actor: User,
    ) -> dict[str, object]:
        """Return persistent weekly working schedule for teacher."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view teacher schedules")

        timezone_name = await self._resolve_teacher_timezone(teacher_id=teacher_id)
        windows = await self.repository.list_teacher_weekly_schedule_windows(teacher_id)
        return self._build_teacher_weekly_schedule_payload(
            teacher_id=teacher_id,
            timezone_name=timezone_name,
            windows=windows,
        )

    async def get_current_teacher_weekly_schedule(
        self,
        *,
        actor: User,
    ) -> dict[str, object]:
        """Return persistent weekly working schedule for current teacher."""
        if actor.role.name != RoleEnum.TEACHER:
            raise UnauthorizedException("Only teacher can view own schedule")

        teacher_id = actor.id
        timezone_name = await self._resolve_teacher_timezone(teacher_id=teacher_id)
        windows = await self.repository.list_teacher_weekly_schedule_windows(teacher_id)
        return self._build_teacher_weekly_schedule_payload(
            teacher_id=teacher_id,
            timezone_name=timezone_name,
            windows=windows,
        )

    async def replace_teacher_weekly_schedule(
        self,
        *,
        teacher_id: UUID,
        windows: list[tuple[int, time, time]],
        actor: User,
    ) -> dict[str, object]:
        """Replace persistent weekly working schedule for teacher."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can update teacher schedules")

        timezone_name = await self._resolve_teacher_timezone(teacher_id=teacher_id)
        normalized_windows = self._normalize_weekly_schedule_windows(windows)
        now_utc = utc_now()

        await self.repository.lock_teacher_for_slot_mutation(teacher_id)
        previous_windows = await self.repository.list_teacher_weekly_schedule_windows(teacher_id)
        updated_windows = await self.repository.replace_teacher_weekly_schedule_windows(
            teacher_id=teacher_id,
            windows=normalized_windows,
        )
        removed_open_slots_count = await self.repository.delete_future_open_slots(
            teacher_id=teacher_id,
            from_utc=now_utc,
        )
        generated_slots_count = await self._materialize_open_slots_from_weekly_schedule(
            teacher_id=teacher_id,
            timezone_name=timezone_name,
            windows=normalized_windows,
            created_by_admin_id=actor.id,
            reference_now_utc=now_utc,
        )

        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="admin.teacher.schedule.replace",
            entity_type="teacher_schedule",
            entity_id=str(teacher_id),
            payload={
                "teacher_id": str(teacher_id),
                "timezone": timezone_name,
                "previous_windows": self._serialize_windows_for_audit(previous_windows),
                "updated_windows": [
                    {
                        "weekday": weekday,
                        "start_local_time": start_local_time.isoformat(),
                        "end_local_time": end_local_time.isoformat(),
                    }
                    for weekday, start_local_time, end_local_time in normalized_windows
                ],
                "removed_open_slots_count": removed_open_slots_count,
                "generated_open_slots_count": generated_slots_count,
            },
        )

        return self._build_teacher_weekly_schedule_payload(
            teacher_id=teacher_id,
            timezone_name=timezone_name,
            windows=updated_windows,
        )

    async def bulk_create_slots(
        self,
        *,
        teacher_id: UUID,
        date_from_utc: date,
        date_to_utc: date,
        weekdays: list[int],
        start_time_utc: time,
        end_time_utc: time,
        slot_duration_minutes: int,
        exclude_dates: list[date] | None,
        exclude_time_ranges: list[tuple[time, time]] | None,
        actor: User,
    ) -> tuple[list[AvailabilitySlot], list[dict[str, object]]]:
        """Create multiple slots by weekly template with deterministic skip reasons."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create slots")
        if date_to_utc < date_from_utc:
            raise BusinessRuleException("date_from_utc must be less than or equal to date_to_utc")
        if end_time_utc <= start_time_utc:
            raise BusinessRuleException("end_time_utc must be after start_time_utc")
        if slot_duration_minutes < settings.slot_min_duration_minutes:
            raise BusinessRuleException(
                f"slot_duration_minutes must be at least {settings.slot_min_duration_minutes}",
            )

        weekdays_set = set(weekdays)
        exclude_dates_set = set(exclude_dates or [])
        exclude_time_ranges_list = exclude_time_ranges or []
        duration = timedelta(minutes=slot_duration_minutes)
        day_count = (date_to_utc - date_from_utc).days + 1
        candidates: list[tuple[datetime, datetime]] = []
        for day_offset in range(day_count):
            current_date = date_from_utc + timedelta(days=day_offset)
            if current_date.weekday() not in weekdays_set:
                continue

            cursor = datetime.combine(current_date, start_time_utc, tzinfo=UTC)
            day_end = datetime.combine(current_date, end_time_utc, tzinfo=UTC)
            while cursor + duration <= day_end:
                candidates.append((cursor, cursor + duration))
                cursor += duration

        if len(candidates) > settings.slot_bulk_create_max_slots:
            raise BusinessRuleException(
                f"Bulk create candidates exceed limit ({settings.slot_bulk_create_max_slots})",
            )

        created_slots: list[AvailabilitySlot] = []
        skipped: list[dict[str, object]] = []
        for start_at_utc, end_at_utc in candidates:
            if start_at_utc.date() in exclude_dates_set:
                skipped.append(
                    {
                        "start_at_utc": start_at_utc,
                        "end_at_utc": end_at_utc,
                        "reason": "excluded_date",
                    },
                )
                continue
            if self._overlaps_excluded_time_ranges(
                start_at_utc=start_at_utc,
                end_at_utc=end_at_utc,
                exclude_time_ranges=exclude_time_ranges_list,
            ):
                skipped.append(
                    {
                        "start_at_utc": start_at_utc,
                        "end_at_utc": end_at_utc,
                        "reason": "excluded_time_range",
                    },
                )
                continue

            try:
                slot = await self.create_slot(
                    SlotCreate(
                        teacher_id=teacher_id,
                        start_at=start_at_utc,
                        end_at=end_at_utc,
                    ),
                    actor,
                )
                created_slots.append(slot)
            except BusinessRuleException as exc:
                skipped.append(
                    {
                        "start_at_utc": start_at_utc,
                        "end_at_utc": end_at_utc,
                        "reason": exc.message,
                    },
                )

        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="admin.slot.bulk_create",
            entity_type="availability_slot_batch",
            entity_id=str(teacher_id),
            payload={
                "teacher_id": str(teacher_id),
                "date_from_utc": date_from_utc.isoformat(),
                "date_to_utc": date_to_utc.isoformat(),
                "weekdays": sorted(weekdays_set),
                "start_time_utc": start_time_utc.isoformat(),
                "end_time_utc": end_time_utc.isoformat(),
                "slot_duration_minutes": slot_duration_minutes,
                "exclude_dates": sorted(item.isoformat() for item in exclude_dates_set),
                "exclude_time_ranges": [
                    {
                        "start_time_utc": start.isoformat(),
                        "end_time_utc": end.isoformat(),
                    }
                    for start, end in exclude_time_ranges_list
                ],
                "created_count": len(created_slots),
                "skipped_count": len(skipped),
            },
        )

        return created_slots, skipped

    @staticmethod
    def _overlaps_excluded_time_ranges(
        *,
        start_at_utc: datetime,
        end_at_utc: datetime,
        exclude_time_ranges: list[tuple[time, time]],
    ) -> bool:
        for range_start, range_end in exclude_time_ranges:
            excluded_start = datetime.combine(start_at_utc.date(), range_start, tzinfo=UTC)
            excluded_end = datetime.combine(start_at_utc.date(), range_end, tzinfo=UTC)
            if start_at_utc < excluded_end and end_at_utc > excluded_start:
                return True
        return False

    async def _materialize_open_slots_from_weekly_schedule(
        self,
        *,
        teacher_id: UUID,
        timezone_name: str,
        windows: list[tuple[int, time, time]],
        created_by_admin_id: UUID,
        reference_now_utc: datetime | None = None,
    ) -> int:
        """Generate upcoming OPEN slots from teacher weekly schedule windows."""
        if not windows:
            return 0

        teacher_zone = self._load_timezone(timezone_name)
        min_duration = timedelta(minutes=settings.slot_min_duration_minutes)
        now_utc = reference_now_utc or utc_now()
        local_today = now_utc.astimezone(teacher_zone).date()

        generated_slots_count = 0
        processed_candidates = 0
        for day_offset in range(AUTO_SLOT_HORIZON_DAYS):
            local_date = local_today + timedelta(days=day_offset)
            weekday = local_date.weekday()
            day_windows = [item for item in windows if item[0] == weekday]
            if not day_windows:
                continue

            for _, start_local_time, end_local_time in day_windows:
                processed_candidates += 1
                if processed_candidates > settings.slot_bulk_create_max_slots:
                    return generated_slots_count

                start_local = datetime.combine(local_date, start_local_time, tzinfo=teacher_zone)
                end_local = datetime.combine(local_date, end_local_time, tzinfo=teacher_zone)
                start_at_utc = start_local.astimezone(UTC)
                end_at_utc = end_local.astimezone(UTC)

                if end_at_utc <= now_utc:
                    continue
                if start_at_utc <= now_utc:
                    next_minute = (now_utc + timedelta(minutes=1)).replace(second=0, microsecond=0)
                    start_at_utc = next_minute
                if end_at_utc - start_at_utc < min_duration:
                    continue

                overlapping_slot = await self.repository.find_overlapping_slot(
                    teacher_id=teacher_id,
                    start_at=start_at_utc,
                    end_at=end_at_utc,
                )
                if overlapping_slot is not None:
                    continue

                await self.repository.create_slot(
                    teacher_id=teacher_id,
                    created_by_admin_id=created_by_admin_id,
                    start_at=start_at_utc,
                    end_at=end_at_utc,
                )
                generated_slots_count += 1

        return generated_slots_count

    async def list_open_slots(
        self,
        teacher_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        """List open slots with pagination."""
        items, total = await self.repository.list_open_slots(
            teacher_id=teacher_id,
            limit=limit,
            offset=offset,
        )
        teacher_ids = list({slot.teacher_id for slot in items})
        teacher_full_names = await self.repository.list_teacher_full_names(teacher_ids)
        serialized_items: list[dict[str, object]] = []
        for slot in items:
            serialized_items.append(
                {
                    "id": slot.id,
                    "teacher_id": slot.teacher_id,
                    "teacher_full_name": teacher_full_names.get(slot.teacher_id),
                    "created_by_admin_id": slot.created_by_admin_id,
                    "start_at": slot.start_at,
                    "end_at": slot.end_at,
                    "status": slot.status,
                    "created_at": slot.created_at,
                    "updated_at": slot.updated_at,
                },
            )
        return serialized_items, total

    async def get_slot_for_booking(self, slot_id: UUID) -> AvailabilitySlot:
        """Return slot that can be used for booking hold."""
        slot = await self.repository.get_slot_by_id(slot_id)
        if slot is None:
            raise NotFoundException("Slot not found")
        if slot.status != SlotStatusEnum.OPEN:
            raise BusinessRuleException("Slot is not available for booking")
        return slot

    async def mark_slot_hold(self, slot: AvailabilitySlot) -> None:
        """Move slot to HOLD state."""
        await self.repository.set_slot_status(slot, SlotStatusEnum.HOLD)

    async def mark_slot_booked(self, slot: AvailabilitySlot) -> None:
        """Move slot to BOOKED state."""
        await self.repository.set_slot_status(slot, SlotStatusEnum.BOOKED)

    async def release_slot(self, slot: AvailabilitySlot) -> None:
        """Return slot to OPEN state."""
        await self.repository.set_slot_status(slot, SlotStatusEnum.OPEN)

    async def _resolve_teacher_timezone(self, *, teacher_id: UUID) -> str:
        timezone_name = await self.repository.get_teacher_timezone(teacher_id)
        if timezone_name is None:
            raise NotFoundException("Teacher not found")
        try:
            self._load_timezone(timezone_name)
        except BusinessRuleException as exc:
            raise BusinessRuleException("Teacher timezone is invalid") from exc
        return timezone_name

    @staticmethod
    def _normalize_weekly_schedule_windows(
        windows: list[tuple[int, time, time]],
    ) -> list[tuple[int, time, time]]:
        if not windows:
            return []
        if len(windows) > 84:
            raise BusinessRuleException("Schedule contains too many windows")

        normalized: list[tuple[int, time, time]] = []
        for weekday, start_local_time, end_local_time in windows:
            normalized_start = start_local_time.replace(second=0, microsecond=0)
            normalized_end = end_local_time.replace(second=0, microsecond=0)
            if weekday < 0 or weekday > 6:
                raise BusinessRuleException("weekday must be in range 0..6")
            if normalized_end <= normalized_start:
                raise BusinessRuleException(
                    "Schedule window end_local_time must be after start_local_time",
                )
            normalized.append((weekday, normalized_start, normalized_end))

        normalized.sort(key=lambda item: (item[0], item[1], item[2]))

        by_weekday: dict[int, list[tuple[time, time]]] = {}
        for weekday, start_local_time, end_local_time in normalized:
            by_weekday.setdefault(weekday, []).append((start_local_time, end_local_time))
        for weekday_windows in by_weekday.values():
            for index in range(1, len(weekday_windows)):
                previous_start, previous_end = weekday_windows[index - 1]
                current_start, current_end = weekday_windows[index]
                if current_start < previous_end:
                    raise BusinessRuleException(
                        "Schedule windows overlap within the same weekday",
                        details={
                            "previous_start_local_time": previous_start.isoformat(),
                            "previous_end_local_time": previous_end.isoformat(),
                            "current_start_local_time": current_start.isoformat(),
                            "current_end_local_time": current_end.isoformat(),
                        },
                    )
        return normalized

    def _build_teacher_weekly_schedule_payload(
        self,
        *,
        teacher_id: UUID,
        timezone_name: str,
        windows: list[TeacherWeeklyScheduleWindow],
    ) -> dict[str, object]:
        teacher_zone = self._load_timezone(timezone_name)
        moscow_zone = self._load_timezone(MOSCOW_TIMEZONE)

        serialized_windows: list[dict[str, object]] = []
        for window in windows:
            weekday = int(window.weekday)
            start_local_time = window.start_local_time
            end_local_time = window.end_local_time
            reference_date = self._next_local_date_for_weekday(
                weekday=weekday,
                timezone_name=timezone_name,
            )
            start_local_datetime = datetime.combine(
                reference_date,
                start_local_time,
                tzinfo=teacher_zone,
            )
            end_local_datetime = datetime.combine(
                reference_date,
                end_local_time,
                tzinfo=teacher_zone,
            )
            start_moscow_datetime = start_local_datetime.astimezone(moscow_zone)
            end_moscow_datetime = end_local_datetime.astimezone(moscow_zone)

            serialized_windows.append(
                {
                    "schedule_window_id": window.id,
                    "weekday": weekday,
                    "start_local_time": start_local_time,
                    "end_local_time": end_local_time,
                    "moscow_start_weekday": start_moscow_datetime.weekday(),
                    "moscow_end_weekday": end_moscow_datetime.weekday(),
                    "moscow_start_time": start_moscow_datetime.time().replace(
                        second=0,
                        microsecond=0,
                    ),
                    "moscow_end_time": end_moscow_datetime.time().replace(second=0, microsecond=0),
                    "created_at_utc": window.created_at,
                    "updated_at_utc": window.updated_at,
                },
            )

        serialized_windows.sort(
            key=lambda item: (
                int(item["weekday"]),
                str(item["start_local_time"]),
                str(item["end_local_time"]),
                str(item["schedule_window_id"]),
            ),
        )
        return {
            "teacher_id": teacher_id,
            "timezone": timezone_name,
            "windows": serialized_windows,
        }

    @staticmethod
    def _next_local_date_for_weekday(*, weekday: int, timezone_name: str) -> date:
        local_today = utc_now().astimezone(SchedulingService._load_timezone(timezone_name)).date()
        days_ahead = (weekday - local_today.weekday()) % 7
        return local_today + timedelta(days=days_ahead)

    @staticmethod
    def _serialize_windows_for_audit(
        windows: list[TeacherWeeklyScheduleWindow],
    ) -> list[dict[str, object]]:
        serialized: list[dict[str, object]] = []
        for window in windows:
            serialized.append(
                {
                    "schedule_window_id": str(window.id),
                    "weekday": int(window.weekday),
                    "start_local_time": window.start_local_time.isoformat(),
                    "end_local_time": window.end_local_time.isoformat(),
                },
            )
        serialized.sort(
            key=lambda item: (
                int(item["weekday"]),
                str(item["start_local_time"]),
                str(item["end_local_time"]),
                str(item["schedule_window_id"]),
            ),
        )
        return serialized

    @staticmethod
    def _load_timezone(timezone_name: str):
        normalized = timezone_name.strip()
        if not normalized:
            raise BusinessRuleException("Teacher timezone is invalid")
        if normalized.upper() in {"UTC", "ETC/UTC", "GMT"}:
            return UTC
        try:
            return ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            if normalized == MOSCOW_TIMEZONE:
                return timezone(timedelta(hours=3))
            raise BusinessRuleException("Teacher timezone is invalid") from exc


async def get_scheduling_service(
    session: AsyncSession = Depends(get_db_session),
) -> SchedulingService:
    """Dependency provider for scheduling service."""
    return SchedulingService(
        repository=SchedulingRepository(session),
        audit_repository=AuditRepository(session),
    )
