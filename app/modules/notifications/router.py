"""Notifications API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.modules.identity.service import get_current_user
from app.modules.notifications.schemas import (
    NotificationCreate,
    NotificationDeliveryMetricsRead,
    NotificationRead,
    NotificationUpdateStatus,
)
from app.modules.notifications.service import NotificationsService, get_notifications_service
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_notification(
    payload: NotificationCreate,
    service: NotificationsService = Depends(get_notifications_service),
    current_user=Depends(get_current_user),
) -> NotificationRead:
    """Create notification."""
    notification = await service.create_notification(payload, current_user)
    return NotificationRead.model_validate(notification)


@router.patch("/{notification_id}/status", response_model=NotificationRead)
async def update_notification_status(
    notification_id: UUID,
    payload: NotificationUpdateStatus,
    service: NotificationsService = Depends(get_notifications_service),
    current_user=Depends(get_current_user),
) -> NotificationRead:
    """Update notification status."""
    notification = await service.update_status(notification_id, payload.status, current_user)
    return NotificationRead.model_validate(notification)


@router.get("/my", response_model=Page[NotificationRead])
async def list_my_notifications(
    pagination=Depends(get_pagination_params),
    service: NotificationsService = Depends(get_notifications_service),
    current_user=Depends(get_current_user),
) -> Page[NotificationRead]:
    """List notifications for current user."""
    items, total = await service.list_my_notifications(current_user, pagination.limit, pagination.offset)
    serialized = [NotificationRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)


@router.get("/delivery/metrics", response_model=NotificationDeliveryMetricsRead)
async def get_delivery_metrics(
    max_retries: int = Query(default=5, ge=1, le=100),
    service: NotificationsService = Depends(get_notifications_service),
    current_user=Depends(get_current_user),
) -> NotificationDeliveryMetricsRead:
    """Return delivery observability metrics."""
    return await service.get_delivery_metrics(current_user, max_retries=max_retries)
