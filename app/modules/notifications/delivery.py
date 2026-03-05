"""Notification delivery clients and result contract."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeliveryMessage:
    """Normalized notification payload for channel delivery."""

    notification_id: UUID
    user_id: UUID
    channel: str
    template_key: str | None
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Delivery attempt result."""

    success: bool
    error_message: str | None = None


class DeliveryClient(Protocol):
    """Notification delivery client contract."""

    async def send(self, message: DeliveryMessage) -> DeliveryResult:
        """Deliver a prepared message and return delivery outcome."""


class StubEmailDeliveryClient:
    """V1 stub provider that only logs delivery attempts."""

    async def send(self, message: DeliveryMessage) -> DeliveryResult:
        logger.info(
            "Stub email delivery: notification_id=%s user_id=%s template_key=%s channel=%s",
            message.notification_id,
            message.user_id,
            message.template_key,
            message.channel,
        )
        return DeliveryResult(success=True)
