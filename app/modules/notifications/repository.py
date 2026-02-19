"""Notifications repository layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import NotificationStatusEnum
from app.modules.notifications.models import Notification


class NotificationsRepository:
    """DB operations for notifications domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_notification(self, user_id: UUID, channel: str, title: str, body: str) -> Notification:
        notification = Notification(user_id=user_id, channel=channel, title=title, body=body)
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def get_notification_by_id(self, notification_id: UUID) -> Notification | None:
        stmt = select(Notification).where(Notification.id == notification_id)
        return await self.session.scalar(stmt)

    async def list_notifications_for_user(self, user_id: UUID, limit: int, offset: int) -> tuple[list[Notification], int]:
        base_stmt: Select[tuple[Notification]] = select(Notification).where(Notification.user_id == user_id)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def set_status(
        self,
        notification: Notification,
        status: NotificationStatusEnum,
        sent_at: datetime | None,
    ) -> Notification:
        notification.status = status
        notification.sent_at = sent_at
        await self.session.flush()
        return notification
