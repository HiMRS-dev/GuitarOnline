from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.core.enums import NotificationStatusEnum, OutboxStatusEnum, RoleEnum
from app.modules.notifications.service import NotificationsService
from app.shared.exceptions import UnauthorizedException


@dataclass
class FakeNotificationsRepository:
    notification_counts: dict[NotificationStatusEnum, int]

    async def count_by_status(self) -> dict[NotificationStatusEnum, int]:
        return self.notification_counts


@dataclass
class FakeAuditRepository:
    outbox_counts: dict[OutboxStatusEnum, int]
    retryable_failed: int
    dead_letter: int

    async def count_outbox_by_status(self) -> dict[OutboxStatusEnum, int]:
        return self.outbox_counts

    async def count_retryable_failed_outbox(self, max_retries: int) -> int:
        return self.retryable_failed

    async def count_dead_letter_outbox(self, max_retries: int) -> int:
        return self.dead_letter


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=role))


@pytest.mark.asyncio
async def test_delivery_metrics_aggregates_notifications_and_outbox_counts() -> None:
    service = NotificationsService(
        repository=FakeNotificationsRepository(
            notification_counts={
                NotificationStatusEnum.PENDING: 3,
                NotificationStatusEnum.SENT: 7,
                NotificationStatusEnum.FAILED: 2,
            },
        ),  # type: ignore[arg-type]
        audit_repository=FakeAuditRepository(
            outbox_counts={
                OutboxStatusEnum.PENDING: 4,
                OutboxStatusEnum.PROCESSED: 10,
                OutboxStatusEnum.FAILED: 5,
            },
            retryable_failed=3,
            dead_letter=2,
        ),  # type: ignore[arg-type]
    )

    metrics = await service.get_delivery_metrics(make_actor(RoleEnum.ADMIN), max_retries=5)

    assert metrics.notifications_total == 12
    assert metrics.notifications_pending == 3
    assert metrics.notifications_sent == 7
    assert metrics.notifications_failed == 2
    assert metrics.outbox_total == 19
    assert metrics.outbox_pending == 4
    assert metrics.outbox_processed == 10
    assert metrics.outbox_failed == 5
    assert metrics.outbox_retryable_failed == 3
    assert metrics.outbox_dead_letter == 2
    assert metrics.max_retries == 5


@pytest.mark.asyncio
async def test_delivery_metrics_defaults_missing_statuses_to_zero() -> None:
    service = NotificationsService(
        repository=FakeNotificationsRepository(notification_counts={}),  # type: ignore[arg-type]
        audit_repository=FakeAuditRepository(
            outbox_counts={OutboxStatusEnum.PENDING: 1},
            retryable_failed=0,
            dead_letter=0,
        ),  # type: ignore[arg-type]
    )

    metrics = await service.get_delivery_metrics(make_actor(RoleEnum.ADMIN), max_retries=3)

    assert metrics.notifications_total == 0
    assert metrics.notifications_pending == 0
    assert metrics.notifications_sent == 0
    assert metrics.notifications_failed == 0
    assert metrics.outbox_total == 1
    assert metrics.outbox_pending == 1
    assert metrics.outbox_processed == 0
    assert metrics.outbox_failed == 0


@pytest.mark.asyncio
async def test_delivery_metrics_requires_admin() -> None:
    service = NotificationsService(
        repository=FakeNotificationsRepository(notification_counts={}),  # type: ignore[arg-type]
        audit_repository=FakeAuditRepository(
            outbox_counts={},
            retryable_failed=0,
            dead_letter=0,
        ),  # type: ignore[arg-type]
    )

    with pytest.raises(UnauthorizedException):
        await service.get_delivery_metrics(make_actor(RoleEnum.STUDENT), max_retries=5)
