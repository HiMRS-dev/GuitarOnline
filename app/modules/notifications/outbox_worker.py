"""Outbox consumer that materializes domain events into notifications."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.enums import NotificationStatusEnum, NotificationTemplateKeyEnum
from app.modules.audit.models import OutboxEvent
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.notifications.delivery import (
    DeliveryClient,
    DeliveryMessage,
    StubEmailDeliveryClient,
)
from app.modules.notifications.repository import NotificationsRepository
from app.modules.notifications.templates import render_template
from app.shared.utils import utc_now

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NotificationMessage:
    user_id: UUID
    title: str
    body: str
    channel: str = "email"
    template_key: str | None = None


class NotificationsOutboxWorker:
    """Process outbox events and create user notifications."""

    def __init__(
        self,
        audit_repository: AuditRepository,
        notifications_repository: NotificationsRepository,
        billing_repository: BillingRepository,
        *,
        batch_size: int = 100,
        max_retries: int = 5,
        base_backoff_seconds: int = 30,
        max_backoff_seconds: int = 300,
        delivery_client: DeliveryClient | None = None,
        now_provider=utc_now,
        commit_callback: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.audit_repository = audit_repository
        self.notifications_repository = notifications_repository
        self.billing_repository = billing_repository
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.delivery_client = delivery_client or StubEmailDeliveryClient()
        self.now_provider = now_provider
        self.commit_callback = commit_callback

    async def run_once(self) -> dict[str, int]:
        """Run one processing cycle."""
        stats = {"requeued": 0, "processed": 0, "failed": 0, "dispatched": 0}
        stats["requeued"] = await self._requeue_retryable_failed_events()

        pending_stats = await self._process_pending_events(limit=self.batch_size)
        stats["processed"] += pending_stats["processed"]
        stats["failed"] += pending_stats["failed"]
        stats["dispatched"] += pending_stats["dispatched"]
        return stats

    async def _process_pending_events(self, *, limit: int) -> dict[str, int]:
        stats = {"processed": 0, "failed": 0, "dispatched": 0}
        if self.commit_callback is None:
            events = await self.audit_repository.claim_pending_outbox(limit=limit)
            for event in events:
                event_stats = await self._process_event(event)
                stats["processed"] += event_stats["processed"]
                stats["failed"] += event_stats["failed"]
                stats["dispatched"] += event_stats["dispatched"]
            return stats

        for _ in range(limit):
            events = await self.audit_repository.claim_pending_outbox(limit=1)
            if not events:
                break
            event_stats = await self._process_event(events[0])
            stats["processed"] += event_stats["processed"]
            stats["failed"] += event_stats["failed"]
            stats["dispatched"] += event_stats["dispatched"]
            await self.commit_callback()
        return stats

    async def _process_event(self, event: OutboxEvent) -> dict[str, int]:
        dispatched = 0
        try:
            messages = await self._build_messages(event)
            for message_index, message in enumerate(messages):
                idempotency_key = self._build_notification_idempotency_key(
                    event=event,
                    message_index=message_index,
                    message=message,
                )
                notification = await self.notifications_repository.get_by_idempotency_key(
                    idempotency_key,
                )
                if notification is None:
                    notification = await self.notifications_repository.create_notification(
                        user_id=message.user_id,
                        channel=message.channel,
                        template_key=message.template_key,
                        title=message.title,
                        body=message.body,
                        idempotency_key=idempotency_key,
                    )

                if notification.status == NotificationStatusEnum.SENT:
                    continue

                delivery_message = DeliveryMessage(
                    notification_id=notification.id,
                    user_id=message.user_id,
                    channel=message.channel,
                    template_key=message.template_key,
                    title=message.title,
                    body=message.body,
                )
                try:
                    delivery_result = await self.delivery_client.send(delivery_message)
                except Exception:
                    await self.notifications_repository.set_status(
                        notification,
                        NotificationStatusEnum.FAILED,
                        None,
                    )
                    logger.exception(
                        "Notification delivery failed: notification_id=%s channel=%s",
                        notification.id,
                        message.channel,
                    )
                    raise

                if not delivery_result.success:
                    error_message = delivery_result.error_message or "Notification delivery failed"
                    await self.notifications_repository.set_status(
                        notification,
                        NotificationStatusEnum.FAILED,
                        None,
                    )
                    logger.warning(
                        "Notification delivery failed: notification_id=%s channel=%s "
                        "error=%s",
                        notification.id,
                        message.channel,
                        error_message,
                    )
                    raise RuntimeError(error_message)

                await self.notifications_repository.set_status(
                    notification,
                    NotificationStatusEnum.SENT,
                    self.now_provider(),
                )
                logger.info(
                    "Notification delivery succeeded: notification_id=%s channel=%s",
                    notification.id,
                    message.channel,
                )
                dispatched += 1

            await self.audit_repository.mark_outbox_processed(event, self.now_provider())
            return {"processed": 1, "failed": 0, "dispatched": dispatched}
        except Exception as exc:
            await self.audit_repository.mark_outbox_failed(event, str(exc))
            return {"processed": 0, "failed": 1, "dispatched": dispatched}

    async def _requeue_retryable_failed_events(self) -> int:
        now = self.now_provider()
        requeued = 0
        if self.commit_callback is None:
            failed_events = await self.audit_repository.claim_retryable_failed_outbox(
                limit=self.batch_size,
                max_retries=self.max_retries,
            )
            for event in failed_events:
                if self._is_backoff_elapsed(event, now):
                    await self.audit_repository.mark_outbox_pending(event)
                    requeued += 1
            return requeued

        for _ in range(self.batch_size):
            failed_events = await self.audit_repository.claim_retryable_failed_outbox(
                limit=1,
                max_retries=self.max_retries,
            )
            if not failed_events:
                break
            event = failed_events[0]
            if self._is_backoff_elapsed(event, now):
                await self.audit_repository.mark_outbox_pending(event)
                requeued += 1
            await self.commit_callback()
        return requeued

    def _is_backoff_elapsed(self, event: OutboxEvent, now: datetime) -> bool:
        retries = max(event.retries, 1)
        backoff_seconds = min(
            self.max_backoff_seconds,
            self.base_backoff_seconds * (2 ** (retries - 1)),
        )
        last_attempt_at = event.updated_at or event.occurred_at
        return now >= last_attempt_at + timedelta(seconds=backoff_seconds)

    @staticmethod
    def _build_notification_idempotency_key(
        *,
        event: OutboxEvent,
        message_index: int,
        message: NotificationMessage,
    ) -> str:
        template_key = message.template_key or "none"
        return (
            f"outbox:{event.id}:{message.user_id}:{message.channel}:{template_key}:{message_index}"
        )[:191]

    def _build_booking_template_contexts(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[tuple[NotificationTemplateKeyEnum, dict[str, Any]]]:
        if event_type == "booking.confirmed":
            return [
                (
                    NotificationTemplateKeyEnum.BOOKING_CONFIRMED,
                    {"booking_id": payload.get("booking_id", "unknown")},
                ),
            ]

        if event_type == "booking.canceled":
            return [
                (
                    NotificationTemplateKeyEnum.BOOKING_CANCELED,
                    {"booking_id": payload.get("booking_id", "unknown")},
                ),
            ]

        if event_type != "booking.rescheduled":
            return []

        template_contexts: list[tuple[NotificationTemplateKeyEnum, dict[str, Any]]] = [
            (
                NotificationTemplateKeyEnum.BOOKING_CANCELED,
                {"booking_id": payload.get("old_booking_id", "unknown")},
            ),
        ]
        include_new_booking_confirmation = payload.get("include_new_booking_confirmation", True)
        if include_new_booking_confirmation:
            template_contexts.append(
                (
                    NotificationTemplateKeyEnum.BOOKING_CONFIRMED,
                    {"booking_id": payload.get("new_booking_id", "unknown")},
                ),
            )
        return template_contexts

    def _build_booking_messages(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[NotificationMessage]:
        template_contexts = self._build_booking_template_contexts(event_type, payload)
        if not template_contexts:
            return []

        student_id = self._required_uuid(payload, "student_id")
        messages: list[NotificationMessage] = []
        for template_key, template_payload in template_contexts:
            rendered = render_template(template_key, template_payload)
            messages.append(
                NotificationMessage(
                    user_id=student_id,
                    template_key=rendered.template_key.value,
                    title=rendered.title,
                    body=rendered.body,
                ),
            )
        return messages

    async def _build_messages(self, event: OutboxEvent) -> list[NotificationMessage]:
        payload = event.payload or {}
        event_type = event.event_type

        if event_type.startswith("booking."):
            return self._build_booking_messages(event_type, payload)

        if event_type in ("lesson.created", "lesson.canceled"):
            title = "Lesson scheduled" if event_type == "lesson.created" else "Lesson canceled"
            lesson_id = payload.get("lesson_id", "unknown")
            recipients = self._unique_recipients(
                self._optional_uuid(payload, "student_id"),
                self._optional_uuid(payload, "teacher_id"),
            )
            return [
                NotificationMessage(
                    user_id=user_id,
                    title=title,
                    body=f"Lesson {lesson_id} status was updated.",
                )
                for user_id in recipients
            ]

        if event_type == "billing.package.created":
            student_id = self._required_uuid(payload, "student_id")
            package_id = payload.get("package_id", "unknown")
            return [
                NotificationMessage(
                    user_id=student_id,
                    title="Package created",
                    body=f"Your package {package_id} is active.",
                ),
            ]

        if event_type == "billing.package.expired":
            student_id = self._required_uuid(payload, "student_id")
            package_id = payload.get("package_id", "unknown")
            return [
                NotificationMessage(
                    user_id=student_id,
                    title="Package expired",
                    body=f"Your package {package_id} has expired.",
                ),
            ]

        if event_type == "billing.payment.status.updated":
            payment_id = self._required_uuid(payload, "payment_id")
            student_id = await self.billing_repository.get_payment_student_id(payment_id)
            if student_id is None:
                raise ValueError(f"Student not found for payment {payment_id}")
            to_status = payload.get("to_status", "unknown")
            return [
                NotificationMessage(
                    user_id=student_id,
                    title="Payment status changed",
                    body=f"Payment {payment_id} status is now {to_status}.",
                ),
            ]

        return []

    @staticmethod
    def _required_uuid(payload: dict, key: str) -> UUID:
        value = payload.get(key)
        if value is None:
            raise ValueError(f"Missing required key: {key}")
        return UUID(str(value))

    @staticmethod
    def _optional_uuid(payload: dict, key: str) -> UUID | None:
        value = payload.get(key)
        if value is None:
            return None
        return UUID(str(value))

    @staticmethod
    def _unique_recipients(*recipients: UUID | None) -> list[UUID]:
        unique: list[UUID] = []
        seen: set[UUID] = set()
        for recipient in recipients:
            if recipient is not None and recipient not in seen:
                unique.append(recipient)
                seen.add(recipient)
        return unique
