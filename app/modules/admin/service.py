"""Admin business logic layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import (
    BookingStatusEnum,
    LessonStatusEnum,
    PackageStatusEnum,
    RoleEnum,
    SlotBookingAggregateStatusEnum,
    SlotStatusEnum,
    TeacherStatusEnum,
)
from app.modules.admin.models import AdminAction
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AdminActionCreate,
    AdminBookingListItemRead,
    AdminKpiOverviewRead,
    AdminOperationsOverviewRead,
    AdminPackageListItemRead,
    AdminSlotBlockRead,
    AdminSlotListItemRead,
    AdminSlotStatsRead,
    AdminTeacherDetailRead,
    AdminTeacherListItemRead,
)
from app.modules.identity.models import User
from app.shared.exceptions import (
    BusinessRuleException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
)
from app.shared.utils import ensure_utc, utc_now


class AdminService:
    """Admin domain service."""

    def __init__(self, repository: AdminRepository) -> None:
        self.repository = repository

    async def create_action(self, payload: AdminActionCreate, actor: User) -> AdminAction:
        """Record admin action."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create admin actions")

        return await self.repository.create_action(
            admin_id=actor.id,
            action=payload.action,
            target_type=payload.target_type,
            target_id=payload.target_id,
            payload=payload.payload,
        )

    async def list_actions(
        self,
        actor: User,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminAction], int]:
        """List admin actions."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can list admin actions")
        return await self.repository.list_actions(limit=limit, offset=offset)

    async def get_kpi_overview(self, actor: User) -> AdminKpiOverviewRead:
        """Return aggregated admin KPI snapshot."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view KPI overview")

        snapshot = await self.repository.get_kpi_overview()
        await self.repository.create_action(
            admin_id=actor.id,
            action="admin.kpi.view",
            target_type="kpi_overview",
            target_id=None,
            payload={"generated_at": snapshot["generated_at"].isoformat()},
        )
        return AdminKpiOverviewRead(**snapshot)

    async def get_operations_overview(
        self,
        actor: User,
        *,
        max_retries: int,
    ) -> AdminOperationsOverviewRead:
        """Return operational snapshot for runbook checks."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view operations overview")

        snapshot = await self.repository.get_operations_overview(max_retries=max_retries)
        await self.repository.create_action(
            admin_id=actor.id,
            action="admin.ops.view",
            target_type="operations_overview",
            target_id=None,
            payload={
                "generated_at": snapshot["generated_at"].isoformat(),
                "max_retries": max_retries,
            },
        )
        return AdminOperationsOverviewRead(**snapshot)

    async def list_teachers(
        self,
        actor: User,
        *,
        limit: int,
        offset: int,
        status: TeacherStatusEnum | None,
        verified: bool | None,
        q: str | None,
        tag: str | None,
    ) -> tuple[list[AdminTeacherListItemRead], int]:
        """List teachers with admin filters for scheduling operations."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can list teachers")

        items, total = await self.repository.list_teachers(
            limit=limit,
            offset=offset,
            status=status,
            verified=verified,
            q=q,
            tag=tag,
        )
        return [AdminTeacherListItemRead.model_validate(item) for item in items], total

    async def get_teacher_detail(
        self,
        actor: User,
        *,
        teacher_id: UUID,
    ) -> AdminTeacherDetailRead:
        """Get teacher detail for admin operations."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view teacher detail")

        item = await self.repository.get_teacher_detail(teacher_id=teacher_id)
        if item is None:
            raise NotFoundException("Teacher profile not found")

        return AdminTeacherDetailRead.model_validate(item)

    async def verify_teacher(
        self,
        actor: User,
        *,
        teacher_id: UUID,
    ) -> AdminTeacherDetailRead:
        """Verify teacher profile and return updated detail."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can verify teachers")

        item = await self.repository.verify_teacher(teacher_id=teacher_id, admin_id=actor.id)
        if item is None:
            raise NotFoundException("Teacher profile not found")
        return AdminTeacherDetailRead.model_validate(item)

    async def disable_teacher(
        self,
        actor: User,
        *,
        teacher_id: UUID,
    ) -> AdminTeacherDetailRead:
        """Disable teacher profile and user account."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can disable teachers")

        item = await self.repository.disable_teacher(teacher_id=teacher_id, admin_id=actor.id)
        if item is None:
            raise NotFoundException("Teacher profile not found")
        return AdminTeacherDetailRead.model_validate(item)

    async def list_slots(
        self,
        actor: User,
        *,
        teacher_id: UUID | None,
        from_utc: datetime | None,
        to_utc: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminSlotListItemRead], int]:
        """List admin slots with aggregated booking status."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can list slots")

        normalized_from_utc = ensure_utc(from_utc) if from_utc is not None else None
        normalized_to_utc = ensure_utc(to_utc) if to_utc is not None else None
        if (
            normalized_from_utc is not None
            and normalized_to_utc is not None
            and normalized_from_utc > normalized_to_utc
        ):
            raise BusinessRuleException("from_utc must be less than or equal to to_utc")

        items, total = await self.repository.list_slots(
            teacher_id=teacher_id,
            from_utc=normalized_from_utc,
            to_utc=normalized_to_utc,
            limit=limit,
            offset=offset,
        )
        serialized: list[AdminSlotListItemRead] = []
        for item in items:
            slot_status = item["slot_status"]
            booking_status = item["booking_status"]
            item["aggregated_booking_status"] = self._aggregate_slot_booking_status(
                slot_status=slot_status,
                booking_status=booking_status,
            )
            serialized.append(AdminSlotListItemRead.model_validate(item))
        return serialized, total

    async def list_bookings(
        self,
        actor: User,
        *,
        teacher_id: UUID | None,
        student_id: UUID | None,
        status: BookingStatusEnum | None,
        from_utc: datetime | None,
        to_utc: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminBookingListItemRead], int]:
        """List bookings for admin booking-management views."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can list bookings")

        normalized_from_utc = ensure_utc(from_utc) if from_utc is not None else None
        normalized_to_utc = ensure_utc(to_utc) if to_utc is not None else None
        if (
            normalized_from_utc is not None
            and normalized_to_utc is not None
            and normalized_from_utc > normalized_to_utc
        ):
            raise BusinessRuleException("from_utc must be less than or equal to to_utc")

        items, total = await self.repository.list_bookings(
            teacher_id=teacher_id,
            student_id=student_id,
            status=status,
            from_utc=normalized_from_utc,
            to_utc=normalized_to_utc,
            limit=limit,
            offset=offset,
        )
        return [AdminBookingListItemRead.model_validate(item) for item in items], total

    async def list_packages(
        self,
        actor: User,
        *,
        student_id: UUID | None,
        status: PackageStatusEnum | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AdminPackageListItemRead], int]:
        """List packages for admin billing-management views."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can list packages")

        items, total = await self.repository.list_packages(
            student_id=student_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [AdminPackageListItemRead.model_validate(item) for item in items], total

    @staticmethod
    def _aggregate_slot_booking_status(
        *,
        slot_status: SlotStatusEnum,
        booking_status: BookingStatusEnum | None,
    ) -> SlotBookingAggregateStatusEnum:
        """Map slot + booking states to admin aggregated booking status."""
        if slot_status == SlotStatusEnum.BOOKED or booking_status == BookingStatusEnum.CONFIRMED:
            return SlotBookingAggregateStatusEnum.CONFIRMED
        if slot_status == SlotStatusEnum.HOLD or booking_status == BookingStatusEnum.HOLD:
            return SlotBookingAggregateStatusEnum.HELD
        return SlotBookingAggregateStatusEnum.OPEN

    async def delete_slot(
        self,
        actor: User,
        *,
        slot_id: UUID,
    ) -> None:
        """Delete slot if it has no related bookings."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can delete slots")

        slot = await self.repository.get_slot_by_id(slot_id)
        if slot is None:
            raise NotFoundException("Slot not found")

        if await self.repository.slot_has_bookings(slot_id):
            raise ConflictException(
                "Slot has related bookings; use POST /api/v1/admin/slots/{slot_id}/block",
            )

        await self.repository.delete_slot(slot=slot, admin_id=actor.id)

    async def block_slot(
        self,
        actor: User,
        *,
        slot_id: UUID,
        reason: str,
    ) -> AdminSlotBlockRead:
        """Block slot with reason and audit trace."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can block slots")

        slot = await self.repository.get_slot_by_id(slot_id)
        if slot is None:
            raise NotFoundException("Slot not found")

        blocked = await self.repository.block_slot(
            slot=slot,
            reason=reason,
            admin_id=actor.id,
            blocked_at=utc_now(),
        )
        return AdminSlotBlockRead(
            slot_id=blocked.id,
            slot_status=blocked.status,
            block_reason=blocked.block_reason,
            blocked_at_utc=blocked.blocked_at,
            blocked_by_admin_id=blocked.blocked_by_admin_id,
            updated_at_utc=blocked.updated_at,
        )

    async def get_slot_stats(
        self,
        actor: User,
        *,
        from_utc: datetime | None,
        to_utc: datetime | None,
    ) -> AdminSlotStatsRead:
        """Return slot stats with single-final-bucket semantics."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view slot stats")

        normalized_from_utc = ensure_utc(from_utc) if from_utc is not None else None
        normalized_to_utc = ensure_utc(to_utc) if to_utc is not None else None
        if (
            normalized_from_utc is not None
            and normalized_to_utc is not None
            and normalized_from_utc > normalized_to_utc
        ):
            raise BusinessRuleException("from_utc must be less than or equal to to_utc")

        rows = await self.repository.list_slot_status_snapshots(
            from_utc=normalized_from_utc,
            to_utc=normalized_to_utc,
        )
        priority = {
            "open": 1,
            "held": 2,
            "confirmed": 3,
            "canceled": 4,
            "completed": 5,
        }
        final_bucket_by_slot: dict[UUID, str] = {}
        for row in rows:
            slot_id = row["slot_id"]
            bucket = self._resolve_slot_stats_bucket(
                slot_status=row["slot_status"],
                booking_status=row["booking_status"],
                lesson_status=row["lesson_status"],
            )
            current_bucket = final_bucket_by_slot.get(slot_id)
            if current_bucket is None or priority[bucket] > priority[current_bucket]:
                final_bucket_by_slot[slot_id] = bucket

        counts = {
            "open": 0,
            "held": 0,
            "confirmed": 0,
            "canceled": 0,
            "completed": 0,
        }
        for bucket in final_bucket_by_slot.values():
            counts[bucket] += 1

        return AdminSlotStatsRead(
            from_utc=normalized_from_utc,
            to_utc=normalized_to_utc,
            total_slots=len(final_bucket_by_slot),
            open_slots=counts["open"],
            held_slots=counts["held"],
            confirmed_slots=counts["confirmed"],
            canceled_slots=counts["canceled"],
            completed_slots=counts["completed"],
        )

    @staticmethod
    def _resolve_slot_stats_bucket(
        *,
        slot_status: SlotStatusEnum,
        booking_status: BookingStatusEnum | None,
        lesson_status: LessonStatusEnum | None,
    ) -> str:
        if lesson_status in {LessonStatusEnum.COMPLETED, LessonStatusEnum.NO_SHOW}:
            return "completed"
        if lesson_status == LessonStatusEnum.CANCELED:
            return "canceled"
        if slot_status in {SlotStatusEnum.CANCELED, SlotStatusEnum.BLOCKED}:
            return "canceled"
        if slot_status == SlotStatusEnum.BOOKED or booking_status == BookingStatusEnum.CONFIRMED:
            return "confirmed"
        if slot_status == SlotStatusEnum.HOLD or booking_status == BookingStatusEnum.HOLD:
            return "held"
        return "open"


async def get_admin_service(session: AsyncSession = Depends(get_db_session)) -> AdminService:
    """Dependency provider for admin service."""
    return AdminService(AdminRepository(session))
