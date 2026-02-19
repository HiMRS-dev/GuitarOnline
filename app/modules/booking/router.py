"""Booking API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.modules.booking.schemas import (
    BookingCancelRequest,
    BookingHoldRequest,
    BookingRead,
    BookingRescheduleRequest,
)
from app.modules.booking.service import BookingService, get_booking_service
from app.modules.identity.service import get_current_user
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/booking", tags=["booking"])


@router.post("/hold", response_model=BookingRead)
async def hold_booking(
    payload: BookingHoldRequest,
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(get_current_user),
) -> BookingRead:
    """Create booking in HOLD state."""
    booking = await service.hold_booking(payload, current_user)
    return BookingRead.model_validate(booking)


@router.post("/{booking_id}/confirm", response_model=BookingRead)
async def confirm_booking(
    booking_id: UUID,
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(get_current_user),
) -> BookingRead:
    """Confirm booking from HOLD to CONFIRMED."""
    booking = await service.confirm_booking(booking_id, current_user)
    return BookingRead.model_validate(booking)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
async def cancel_booking(
    booking_id: UUID,
    payload: BookingCancelRequest,
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(get_current_user),
) -> BookingRead:
    """Cancel booking and apply refund policy."""
    booking = await service.cancel_booking(booking_id, payload, current_user)
    return BookingRead.model_validate(booking)


@router.post("/{booking_id}/reschedule", response_model=BookingRead)
async def reschedule_booking(
    booking_id: UUID,
    payload: BookingRescheduleRequest,
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(get_current_user),
) -> BookingRead:
    """Reschedule booking using cancel + new booking flow."""
    booking = await service.reschedule_booking(booking_id, payload, current_user)
    return BookingRead.model_validate(booking)


@router.post("/holds/expire", response_model=int)
async def expire_booking_holds(
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(get_current_user),
) -> int:
    """Expire stale holds (admin task endpoint)."""
    return await service.expire_holds(current_user)


@router.get("/my", response_model=Page[BookingRead])
async def list_my_bookings(
    pagination=Depends(get_pagination_params),
    service: BookingService = Depends(get_booking_service),
    current_user=Depends(get_current_user),
) -> Page[BookingRead]:
    """List bookings for current user."""
    items, total = await service.list_bookings(current_user, pagination.limit, pagination.offset)
    serialized = [BookingRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)
