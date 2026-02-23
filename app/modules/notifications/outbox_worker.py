"""Outbox consumer that materializes domain events into notifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.core.enums import NotificationStatusEnum
from app.modules.audit.models import OutboxEvent
from app.modules.audit.repository import AuditRepository
from app.modules.billing.repository import BillingRepository
from app.modules.notifications.repository import NotificationsRepository
from app.shared.utils import utc_now


@dataclass(slots=True)
class NotificationMessage:
    user_id: UUID
    title: str
    body: str
    channel: str = "email"


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
        now_provider=utc_now,
    ) -> None:
        self.audit_repository = audit_repository
        self.notifications_repository = notifications_repository
        self.billing_repository = billing_repository
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.now_provider = now_provider

    async def run_once(self) -> dict[str, int]:
        """Run one processing cycle."""
        stats = {"requeued": 0, "processed": 0, "failed": 0, "dispatched": 0}
        stats["requeued"] = await self._requeue_retryable_failed_events()

        events = await self.audit_repository.list_pending_outbox(limit=self.batch_size)
        for event in events:
            try:
                messages = await self._build_messages(event)
                for message in messages:
                    notification = await self.notifications_repository.create_notification(
                        user_id=message.user_id,
                        channel=message.channel,
                        title=message.title,
                        body=message.body,
                    )
                    await self.notifications_repository.set_status(
                        notification,
                        NotificationStatusEnum.SENT,
                        self.now_provider(),
                    )
                    stats["dispatched"] += 1

                await self.audit_repository.mark_outbox_processed(event, self.now_provider())
                stats["processed"] += 1
            except Exception as exc:
                await self.audit_repository.mark_outbox_failed(event, str(exc))
                stats["failed"] += 1
        return stats

    async def _requeue_retryable_failed_events(self) -> int:
        now = self.now_provider()
        failed_events = await self.audit_repository.list_failed_outbox(
            limit=self.batch_size,
            max_retries=self.max_retries,
        )
        requeued = 0
        for event in failed_events:
            if self._is_backoff_elapsed(event, now):
                await self.audit_repository.mark_outbox_pending(event)
                requeued += 1
        return requeued

    def _is_backoff_elapsed(self, event: OutboxEvent, now: datetime) -> bool:
        retries = max(event.retries, 1)
        backoff_seconds = min(
            self.max_backoff_seconds,
            self.base_backoff_seconds * (2 ** (retries - 1)),
        )
        last_attempt_at = event.updated_at or event.occurred_at
        return now >= last_attempt_at + timedelta(seconds=backoff_seconds)

    async def _build_messages(self, event: OutboxEvent) -> list[NotificationMessage]:
        payload = event.payload or {}
        event_type = event.event_type

        if event_type == "booking.confirmed":
            student_id = self._required_uuid(payload, "student_id")
            booking_id = payload.get("booking_id", "unknown")
            return [
                NotificationMessage(
                    user_id=student_id,
                    title="Booking confirmed",
                    body=f"Your booking {booking_id} has been confirmed.",
                ),
            ]

        if event_type == "booking.canceled":
            student_id = self._required_uuid(payload, "student_id")
            booking_id = payload.get("booking_id", "unknown")
            return [
                NotificationMessage(
                    user_id=student_id,
                    title="Booking canceled",
                    body=f"Your booking {booking_id} has been canceled.",
                ),
            ]

        if event_type == "booking.rescheduled":
            student_id = self._required_uuid(payload, "student_id")
            new_booking_id = payload.get("new_booking_id", "unknown")
            old_booking_id = payload.get("old_booking_id", "unknown")
            return [
                NotificationMessage(
                    user_id=student_id,
                    title="Booking rescheduled",
                    body=f"Booking moved from {old_booking_id} to {new_booking_id}.",
                ),
            ]

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
