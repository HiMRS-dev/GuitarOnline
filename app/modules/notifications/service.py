"""Notifications business logic layer."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import NotificationStatusEnum, RoleEnum
from app.modules.identity.models import User
from app.modules.notifications.models import Notification
from app.modules.notifications.repository import NotificationsRepository
from app.modules.notifications.schemas import NotificationCreate
from app.shared.exceptions import NotFoundException, UnauthorizedException
from app.shared.utils import utc_now


class NotificationsService:
    """Notifications domain service."""

    def __init__(self, repository: NotificationsRepository) -> None:
        self.repository = repository

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


async def get_notifications_service(session: AsyncSession = Depends(get_db_session)) -> NotificationsService:
    """Dependency provider for notifications service."""
    return NotificationsService(NotificationsRepository(session))
