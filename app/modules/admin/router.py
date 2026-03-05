"""Admin API router."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.enums import BookingStatusEnum, PackageStatusEnum, RoleEnum, TeacherStatusEnum
from app.modules.admin.schemas import (
    AdminActionCreate,
    AdminActionRead,
    AdminBookingCancelRequest,
    AdminBookingListItemRead,
    AdminBookingRescheduleRequest,
    AdminKpiOverviewRead,
    AdminOperationsOverviewRead,
    AdminPackageCreateRead,
    AdminPackageCreateRequest,
    AdminPackageListItemRead,
    AdminSlotBlockRead,
    AdminSlotBlockRequest,
    AdminSlotBulkCreateRead,
    AdminSlotBulkCreateRequest,
    AdminSlotCreateRead,
    AdminSlotCreateRequest,
    AdminSlotListItemRead,
    AdminSlotStatsRead,
    AdminTeacherDetailRead,
    AdminTeacherListItemRead,
)
from app.modules.admin.service import AdminService, get_admin_service
from app.modules.billing.schemas import PackageCreateAdmin
from app.modules.billing.service import BillingService, get_billing_service
from app.modules.booking.schemas import BookingCancelRequest, BookingRead, BookingRescheduleRequest
from app.modules.booking.service import BookingService, get_booking_service
from app.modules.identity.service import require_roles
from app.modules.lessons.schemas import LessonRead
from app.modules.lessons.service import LessonsService, get_lessons_service
from app.modules.scheduling.schemas import SlotCreate
from app.modules.scheduling.service import SchedulingService, get_scheduling_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/actions", response_model=AdminActionRead, status_code=status.HTTP_201_CREATED)
async def create_admin_action(
    payload: AdminActionCreate,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminActionRead:
    """Create admin action log."""
    action = await service.create_action(payload, current_user)
    return AdminActionRead.model_validate(action)


@router.get("/actions", response_model=Page[AdminActionRead])
async def list_admin_actions(
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminActionRead]:
    """List admin action logs."""
    items, total = await service.list_actions(current_user, pagination.limit, pagination.offset)
    serialized = [AdminActionRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)


@router.get("/teachers", response_model=Page[AdminTeacherListItemRead])
async def list_admin_teachers(
    status_filter: TeacherStatusEnum | None = Query(default=None, alias="status"),
    verified: bool | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=255),
    tag: str | None = Query(default=None, min_length=1, max_length=64),
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminTeacherListItemRead]:
    """List teachers for admin filters by status/verification/query/tag."""
    items, total = await service.list_teachers(
        current_user,
        limit=pagination.limit,
        offset=pagination.offset,
        status=status_filter,
        verified=verified,
        q=q,
        tag=tag,
    )
    return build_page(items, total, pagination)


@router.get("/teachers/{teacher_id}", response_model=AdminTeacherDetailRead)
async def get_admin_teacher_detail(
    teacher_id: UUID,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminTeacherDetailRead:
    """Get teacher detail for admin views."""
    return await service.get_teacher_detail(current_user, teacher_id=teacher_id)


@router.post("/teachers/{teacher_id}/verify", response_model=AdminTeacherDetailRead)
async def verify_admin_teacher(
    teacher_id: UUID,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminTeacherDetailRead:
    """Verify teacher profile from admin panel."""
    return await service.verify_teacher(current_user, teacher_id=teacher_id)


@router.post("/teachers/{teacher_id}/disable", response_model=AdminTeacherDetailRead)
async def disable_admin_teacher(
    teacher_id: UUID,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminTeacherDetailRead:
    """Disable teacher profile from admin panel."""
    return await service.disable_teacher(current_user, teacher_id=teacher_id)


@router.post("/slots", response_model=AdminSlotCreateRead, status_code=status.HTTP_201_CREATED)
async def create_admin_slot(
    payload: AdminSlotCreateRequest,
    service: SchedulingService = Depends(get_scheduling_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminSlotCreateRead:
    """Create availability slot with strict admin validation."""
    slot = await service.create_slot(
        SlotCreate(
            teacher_id=payload.teacher_id,
            start_at=payload.start_at_utc,
            end_at=payload.end_at_utc,
        ),
        current_user,
    )
    return AdminSlotCreateRead(
        slot_id=slot.id,
        teacher_id=slot.teacher_id,
        created_by_admin_id=slot.created_by_admin_id,
        start_at_utc=slot.start_at,
        end_at_utc=slot.end_at,
        slot_status=slot.status,
        created_at_utc=slot.created_at,
        updated_at_utc=slot.updated_at,
    )


@router.get("/slots", response_model=Page[AdminSlotListItemRead])
async def list_admin_slots(
    teacher_id: UUID | None = Query(default=None),
    from_utc: datetime | None = Query(default=None),
    to_utc: datetime | None = Query(default=None),
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminSlotListItemRead]:
    """List slots for admin calendar views with aggregated booking status."""
    items, total = await service.list_slots(
        current_user,
        teacher_id=teacher_id,
        from_utc=from_utc,
        to_utc=to_utc,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(items, total, pagination)


@router.get("/bookings", response_model=Page[AdminBookingListItemRead])
async def list_admin_bookings(
    teacher_id: UUID | None = Query(default=None),
    student_id: UUID | None = Query(default=None),
    status_filter: BookingStatusEnum | None = Query(default=None, alias="status"),
    from_utc: datetime | None = Query(default=None),
    to_utc: datetime | None = Query(default=None),
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminBookingListItemRead]:
    """List bookings for admin operations with filters."""
    items, total = await service.list_bookings(
        current_user,
        teacher_id=teacher_id,
        student_id=student_id,
        status=status_filter,
        from_utc=from_utc,
        to_utc=to_utc,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(items, total, pagination)


@router.get("/packages", response_model=Page[AdminPackageListItemRead])
async def list_admin_packages(
    student_id: UUID | None = Query(default=None),
    status_filter: PackageStatusEnum | None = Query(default=None, alias="status"),
    pagination=Depends(get_pagination_params),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Page[AdminPackageListItemRead]:
    """List lesson packages for admin billing operations with filters."""
    items, total = await service.list_packages(
        current_user,
        student_id=student_id,
        status=status_filter,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return build_page(items, total, pagination)


@router.post(
    "/packages",
    response_model=AdminPackageCreateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_package(
    payload: AdminPackageCreateRequest,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminPackageCreateRead:
    """Create manual package with price snapshot under admin contract."""
    package = await service.create_admin_package(
        PackageCreateAdmin(
            student_id=payload.student_id,
            lessons_total=payload.lessons_total,
            expires_at=payload.expires_at_utc,
            price_amount=payload.price_amount,
            price_currency=payload.price_currency,
        ),
        current_user,
    )
    return AdminPackageCreateRead(
        package_id=package.id,
        student_id=package.student_id,
        lessons_total=package.lessons_total,
        lessons_left=package.lessons_left,
        price_amount=package.price_amount,
        price_currency=package.price_currency,
        expires_at_utc=package.expires_at,
        status=package.status,
        created_at_utc=package.created_at,
        updated_at_utc=package.updated_at,
    )


@router.post("/bookings/{booking_id}/cancel", response_model=BookingRead)
async def cancel_admin_booking(
    booking_id: UUID,
    payload: AdminBookingCancelRequest,
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> BookingRead:
    """Cancel booking via admin-only flow with explicit reason."""
    booking = await service.cancel_booking(
        booking_id,
        BookingCancelRequest(reason=payload.reason),
        current_user,
    )
    return BookingRead.model_validate(booking)


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingRead)
async def reschedule_admin_booking(
    booking_id: UUID,
    payload: AdminBookingRescheduleRequest,
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> BookingRead:
    """Reschedule booking via admin-only atomic flow."""
    booking = await service.reschedule_booking(
        booking_id,
        BookingRescheduleRequest(new_slot_id=payload.new_slot_id, reason=payload.reason),
        current_user,
    )
    return BookingRead.model_validate(booking)


@router.post("/lessons/{lesson_id}/no-show", response_model=LessonRead)
async def mark_admin_lesson_no_show(
    lesson_id: UUID,
    service: LessonsService = Depends(get_lessons_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> LessonRead:
    """Mark lesson as NO_SHOW via admin-only operation."""
    lesson = await service.mark_no_show(lesson_id, current_user)
    return LessonRead.model_validate(lesson)


@router.delete("/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_slot(
    slot_id: UUID,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> Response:
    """Delete slot when no related bookings exist."""
    await service.delete_slot(current_user, slot_id=slot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/slots/{slot_id}/block", response_model=AdminSlotBlockRead)
async def block_admin_slot(
    slot_id: UUID,
    payload: AdminSlotBlockRequest,
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminSlotBlockRead:
    """Block slot and persist reason with audit trace."""
    return await service.block_slot(current_user, slot_id=slot_id, reason=payload.reason)


@router.post("/slots/bulk-create", response_model=AdminSlotBulkCreateRead)
async def bulk_create_admin_slots(
    payload: AdminSlotBulkCreateRequest,
    service: SchedulingService = Depends(get_scheduling_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminSlotBulkCreateRead:
    """Bulk create slots from admin schedule template."""
    created_slots, skipped = await service.bulk_create_slots(
        teacher_id=payload.teacher_id,
        date_from_utc=payload.date_from_utc,
        date_to_utc=payload.date_to_utc,
        weekdays=payload.weekdays,
        start_time_utc=payload.start_time_utc,
        end_time_utc=payload.end_time_utc,
        slot_duration_minutes=payload.slot_duration_minutes,
        exclude_dates=payload.exclude_dates,
        exclude_time_ranges=[
            (item.start_time_utc, item.end_time_utc) for item in payload.exclude_time_ranges
        ],
        actor=current_user,
    )
    return AdminSlotBulkCreateRead(
        created_count=len(created_slots),
        skipped_count=len(skipped),
        created_slot_ids=[slot.id for slot in created_slots],
        skipped=skipped,
    )


@router.get("/slots/stats", response_model=AdminSlotStatsRead)
async def get_admin_slot_stats(
    from_utc: datetime | None = Query(default=None),
    to_utc: datetime | None = Query(default=None),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminSlotStatsRead:
    """Return admin slot stats with final bucket semantics."""
    return await service.get_slot_stats(
        current_user,
        from_utc=from_utc,
        to_utc=to_utc,
    )


@router.get("/kpi/overview", response_model=AdminKpiOverviewRead)
async def get_admin_kpi_overview(
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminKpiOverviewRead:
    """Get admin KPI overview snapshot."""
    return await service.get_kpi_overview(current_user)


@router.get("/ops/overview", response_model=AdminOperationsOverviewRead)
async def get_admin_operations_overview(
    max_retries: int = Query(default=5, ge=1, le=100),
    service: AdminService = Depends(get_admin_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> AdminOperationsOverviewRead:
    """Get operational overview snapshot."""
    return await service.get_operations_overview(current_user, max_retries=max_retries)
