"""Notifications business logic layer."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import NotificationStatusEnum, OutboxStatusEnum, RoleEnum
from app.modules.audit.repository import AuditRepository
from app.modules.identity.models import User
from app.modules.notifications.models import Notification
from app.modules.notifications.repository import NotificationsRepository
from app.modules.notifications.schemas import NotificationCreate, NotificationDeliveryMetricsRead
from app.shared.exceptions import NotFoundException, UnauthorizedException
from app.shared.utils import utc_now


class NotificationsService:
    """Notifications domain service."""

    def __init__(
        self,
        repository: NotificationsRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.repository = repository
        self.audit_repository = audit_repository

    async def create_notification(self, payload: NotificationCreate, actor: User) -> Notification:
        """Create notification entity."""
        if actor.role.name not in (RoleEnum.ADMIN, RoleEnum.TEACHER):
            raise UnauthorizedException("Only admin and teacher can create notifications")
        return await self.repository.create_notification(
            user_id=payload.user_id,
            channel=payload.channel,
            title=payload.title,
            body=payload.body,
        )

    async def update_status(self, notification_id, status: NotificationStatusEnum, actor: User) -> Notification:
        """Update notification status."""
        notification = await self.repository.get_notification_by_id(notification_id)
        if notification is None:
            raise NotFoundException("Notification not found")

        if actor.role.name != RoleEnum.ADMIN and notification.user_id != actor.id:
            raise UnauthorizedException("Only admin or recipient can update notification")

        sent_at = utc_now() if status == NotificationStatusEnum.SENT else None
        return await self.repository.set_status(notification, status, sent_at)

    async def list_my_notifications(self, actor: User, limit: int, offset: int) -> tuple[list[Notification], int]:
        """List notifications for current user."""
        return await self.repository.list_notifications_for_user(actor.id, limit, offset)

    async def get_delivery_metrics(self, actor: User, max_retries: int) -> NotificationDeliveryMetricsRead:
        """Return delivery pipeline snapshot (admin only)."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can view delivery metrics")

        notification_counts = await self.repository.count_by_status()
        outbox_counts = await self.audit_repository.count_outbox_by_status()
        retryable_failed = await self.audit_repository.count_retryable_failed_outbox(max_retries=max_retries)
        dead_letter = await self.audit_repository.count_dead_letter_outbox(max_retries=max_retries)

        notifications_pending = notification_counts.get(NotificationStatusEnum.PENDING, 0)
        notifications_sent = notification_counts.get(NotificationStatusEnum.SENT, 0)
        notifications_failed = notification_counts.get(NotificationStatusEnum.FAILED, 0)

        outbox_pending = outbox_counts.get(OutboxStatusEnum.PENDING, 0)
        outbox_processed = outbox_counts.get(OutboxStatusEnum.PROCESSED, 0)
        outbox_failed = outbox_counts.get(OutboxStatusEnum.FAILED, 0)

        return NotificationDeliveryMetricsRead(
            notifications_total=notifications_pending + notifications_sent + notifications_failed,
            notifications_pending=notifications_pending,
            notifications_sent=notifications_sent,
            notifications_failed=notifications_failed,
            outbox_total=outbox_pending + outbox_processed + outbox_failed,
            outbox_pending=outbox_pending,
            outbox_processed=outbox_processed,
            outbox_failed=outbox_failed,
            outbox_retryable_failed=retryable_failed,
            outbox_dead_letter=dead_letter,
            max_retries=max_retries,
        )


async def get_notifications_service(session: AsyncSession = Depends(get_db_session)) -> NotificationsService:
    """Dependency provider for notifications service."""
    return NotificationsService(
        repository=NotificationsRepository(session),
        audit_repository=AuditRepository(session),
    )
