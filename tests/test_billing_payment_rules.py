from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import app.modules.billing.service as billing_service_module
from app.core.enums import PaymentStatusEnum, RoleEnum
from app.modules.billing.service import BillingService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


@dataclass
class FakePayment:
    id: UUID
    status: PaymentStatusEnum
    paid_at: datetime | None = None


class FakeBillingRepository:
    def __init__(self, payments: dict[UUID, FakePayment]) -> None:
        self._payments = payments

    async def get_payment_by_id(self, payment_id: UUID) -> FakePayment | None:
        return self._payments.get(payment_id)

    async def set_payment_status(
        self,
        payment: FakePayment,
        status: PaymentStatusEnum,
        paid_at: datetime | None,
    ) -> FakePayment:
        payment.status = status
        payment.paid_at = paid_at
        return payment


class FakeAuditRepository:
    def __init__(self) -> None:
        self.audit_logs: list[dict] = []
        self.outbox_events: list[dict] = []

    async def create_audit_log(
        self,
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict,
    ) -> None:
        self.audit_logs.append(
            {
                "actor_id": str(actor_id) if actor_id is not None else None,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload,
            },
        )

    async def create_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        self.outbox_events.append(
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": payload,
            },
        )


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_service(payments: dict[UUID, FakePayment]) -> tuple[BillingService, FakeAuditRepository]:
    audit_repo = FakeAuditRepository()
    service = BillingService(
        repository=FakeBillingRepository(payments),
        audit_repository=audit_repo,
    )
    return service, audit_repo


@pytest.mark.asyncio
async def test_update_payment_status_pending_to_succeeded_sets_paid_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 23, 10, 0, tzinfo=UTC)
    monkeypatch.setattr(billing_service_module, "utc_now", lambda: fixed_now)

    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service, audit_repo = make_service({payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, admin)

    assert updated.status == PaymentStatusEnum.SUCCEEDED
    assert updated.paid_at == fixed_now
    assert len(audit_repo.audit_logs) == 1
    assert audit_repo.audit_logs[0]["action"] == "billing.payment.status.update"
    assert len(audit_repo.outbox_events) == 1
    assert audit_repo.outbox_events[0]["event_type"] == "billing.payment.status.updated"


@pytest.mark.asyncio
async def test_update_payment_status_is_idempotent_for_same_status() -> None:
    paid_at = datetime(2026, 2, 23, 10, 30, tzinfo=UTC)
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.SUCCEEDED, paid_at=paid_at)
    service, audit_repo = make_service({payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, admin)

    assert updated.status == PaymentStatusEnum.SUCCEEDED
    assert updated.paid_at == paid_at
    assert len(audit_repo.audit_logs) == 0
    assert len(audit_repo.outbox_events) == 0


@pytest.mark.asyncio
async def test_update_payment_status_allows_failed_to_pending_for_reconciliation() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.FAILED, paid_at=None)
    service, _ = make_service({payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.PENDING, admin)

    assert updated.status == PaymentStatusEnum.PENDING
    assert updated.paid_at is None


@pytest.mark.asyncio
async def test_update_payment_status_rejects_invalid_transition() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service, _ = make_service({payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.update_payment_status(payment_id, PaymentStatusEnum.REFUNDED, admin)


@pytest.mark.asyncio
async def test_update_payment_status_preserves_paid_at_on_refund() -> None:
    paid_at = datetime(2026, 2, 23, 9, 0, tzinfo=UTC)
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.SUCCEEDED, paid_at=paid_at)
    service, _ = make_service({payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.REFUNDED, admin)

    assert updated.status == PaymentStatusEnum.REFUNDED
    assert updated.paid_at == paid_at


@pytest.mark.asyncio
async def test_update_payment_status_requires_admin() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service, _ = make_service({payment_id: payment})
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, student)
