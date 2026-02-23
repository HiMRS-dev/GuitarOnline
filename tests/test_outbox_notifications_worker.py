from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.enums import NotificationStatusEnum, OutboxStatusEnum
from app.modules.notifications.outbox_worker import NotificationsOutboxWorker


@dataclass
class FakeOutboxEvent:
    id: UUID
    event_type: str
    payload: dict
    status: OutboxStatusEnum = OutboxStatusEnum.PENDING
    retries: int = 0
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None
    error_message: str | None = None


@dataclass
class FakeNotification:
    id: UUID
    user_id: UUID
    channel: str
    title: str
    body: str
    status: NotificationStatusEnum = NotificationStatusEnum.PENDING
    sent_at: datetime | None = None


class FakeAuditRepository:
    def __init__(self, events: list[FakeOutboxEvent]) -> None:
        self.events = events

    async def list_pending_outbox(self, limit: int) -> list[FakeOutboxEvent]:
        return [event for event in self.events if event.status == OutboxStatusEnum.PENDING][:limit]

    async def list_failed_outbox(self, limit: int, max_retries: int) -> list[FakeOutboxEvent]:
        return [
            event
            for event in self.events
            if event.status == OutboxStatusEnum.FAILED and event.retries < max_retries
        ][:limit]

    async def mark_outbox_pending(self, event: FakeOutboxEvent) -> FakeOutboxEvent:
        event.status = OutboxStatusEnum.PENDING
        event.error_message = None
        event.updated_at = datetime.now(UTC)
        return event

    async def mark_outbox_processed(
        self,
        event: FakeOutboxEvent,
        processed_at: datetime,
    ) -> FakeOutboxEvent:
        event.status = OutboxStatusEnum.PROCESSED
        event.processed_at = processed_at
        event.error_message = None
        event.updated_at = processed_at
        return event

    async def mark_outbox_failed(
        self,
        event: FakeOutboxEvent,
        error_message: str,
    ) -> FakeOutboxEvent:
        event.status = OutboxStatusEnum.FAILED
        event.retries += 1
        event.error_message = error_message
        event.updated_at = datetime.now(UTC)
        return event


class FakeNotificationsRepository:
    def __init__(self) -> None:
        self.notifications: list[FakeNotification] = []

    async def create_notification(
        self,
        user_id: UUID,
        channel: str,
        title: str,
        body: str,
    ) -> FakeNotification:
        notification = FakeNotification(
            id=uuid4(),
            user_id=user_id,
            channel=channel,
            title=title,
            body=body,
        )
        self.notifications.append(notification)
        return notification

    async def set_status(
        self,
        notification: FakeNotification,
        status: NotificationStatusEnum,
        sent_at: datetime | None,
    ) -> FakeNotification:
        notification.status = status
        notification.sent_at = sent_at
        return notification


class FakeBillingRepository:
    def __init__(self, payment_to_student: dict[UUID, UUID] | None = None) -> None:
        self.payment_to_student = payment_to_student or {}

    async def get_payment_student_id(self, payment_id: UUID) -> UUID | None:
        return self.payment_to_student.get(payment_id)


def make_worker(
    events: list[FakeOutboxEvent],
    *,
    payment_to_student: dict[UUID, UUID] | None = None,
    now: datetime | None = None,
    base_backoff_seconds: int = 30,
) -> tuple[NotificationsOutboxWorker, FakeAuditRepository, FakeNotificationsRepository]:
    now_point = now or datetime.now(UTC)
    audit_repo = FakeAuditRepository(events)
    notifications_repo = FakeNotificationsRepository()
    billing_repo = FakeBillingRepository(payment_to_student)
    worker = NotificationsOutboxWorker(
        audit_repository=audit_repo,  # type: ignore[arg-type]
        notifications_repository=notifications_repo,  # type: ignore[arg-type]
        billing_repository=billing_repo,  # type: ignore[arg-type]
        now_provider=lambda: now_point,
        base_backoff_seconds=base_backoff_seconds,
    )
    return worker, audit_repo, notifications_repo


@pytest.mark.asyncio
async def test_worker_processes_booking_confirmed_into_notification() -> None:
    student_id = uuid4()
    event = FakeOutboxEvent(
        id=uuid4(),
        event_type="booking.confirmed",
        payload={"student_id": str(student_id), "booking_id": str(uuid4())},
    )
    worker, _, notifications_repo = make_worker(
        [event],
        now=datetime(2026, 2, 23, 12, 0, tzinfo=UTC),
    )

    stats = await worker.run_once()

    assert stats == {"requeued": 0, "processed": 1, "failed": 0, "dispatched": 1}
    assert event.status == OutboxStatusEnum.PROCESSED
    assert len(notifications_repo.notifications) == 1
    assert notifications_repo.notifications[0].user_id == student_id
    assert notifications_repo.notifications[0].status == NotificationStatusEnum.SENT


@pytest.mark.asyncio
async def test_worker_processes_unknown_event_without_dispatch() -> None:
    event = FakeOutboxEvent(
        id=uuid4(),
        event_type="unknown.event",
        payload={},
    )
    worker, _, notifications_repo = make_worker(
        [event],
        now=datetime(2026, 2, 23, 12, 0, tzinfo=UTC),
    )

    stats = await worker.run_once()

    assert stats == {"requeued": 0, "processed": 1, "failed": 0, "dispatched": 0}
    assert event.status == OutboxStatusEnum.PROCESSED
    assert notifications_repo.notifications == []


@pytest.mark.asyncio
async def test_worker_resolves_payment_status_event_recipient() -> None:
    payment_id = uuid4()
    student_id = uuid4()
    event = FakeOutboxEvent(
        id=uuid4(),
        event_type="billing.payment.status.updated",
        payload={"payment_id": str(payment_id), "to_status": "succeeded"},
    )
    worker, _, notifications_repo = make_worker(
        [event],
        payment_to_student={payment_id: student_id},
        now=datetime(2026, 2, 23, 12, 0, tzinfo=UTC),
    )

    stats = await worker.run_once()

    assert stats["failed"] == 0
    assert stats["dispatched"] == 1
    assert notifications_repo.notifications[0].user_id == student_id


@pytest.mark.asyncio
async def test_worker_requeues_failed_event_after_backoff() -> None:
    student_id = uuid4()
    now_point = datetime(2026, 2, 23, 12, 0, tzinfo=UTC)
    event = FakeOutboxEvent(
        id=uuid4(),
        event_type="booking.canceled",
        payload={"student_id": str(student_id), "booking_id": str(uuid4())},
        status=OutboxStatusEnum.FAILED,
        retries=1,
        occurred_at=now_point - timedelta(minutes=10),
        updated_at=now_point - timedelta(minutes=2),
    )
    worker, _, notifications_repo = make_worker(
        [event],
        now=now_point,
        base_backoff_seconds=30,
    )

    stats = await worker.run_once()

    assert stats["requeued"] == 1
    assert stats["processed"] == 1
    assert event.status == OutboxStatusEnum.PROCESSED
    assert len(notifications_repo.notifications) == 1


@pytest.mark.asyncio
async def test_worker_marks_event_failed_when_payload_invalid() -> None:
    event = FakeOutboxEvent(
        id=uuid4(),
        event_type="booking.confirmed",
        payload={},
    )
    worker, _, notifications_repo = make_worker(
        [event],
        now=datetime(2026, 2, 23, 12, 0, tzinfo=UTC),
    )

    stats = await worker.run_once()

    assert stats["processed"] == 0
    assert stats["failed"] == 1
    assert event.status == OutboxStatusEnum.FAILED
    assert event.retries == 1
    assert notifications_repo.notifications == []
