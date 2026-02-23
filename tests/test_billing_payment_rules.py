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


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


@pytest.mark.asyncio
async def test_update_payment_status_pending_to_succeeded_sets_paid_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 23, 10, 0, tzinfo=UTC)
    monkeypatch.setattr(billing_service_module, "utc_now", lambda: fixed_now)

    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service = BillingService(FakeBillingRepository({payment_id: payment}))
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, admin)

    assert updated.status == PaymentStatusEnum.SUCCEEDED
    assert updated.paid_at == fixed_now


@pytest.mark.asyncio
async def test_update_payment_status_is_idempotent_for_same_status() -> None:
    paid_at = datetime(2026, 2, 23, 10, 30, tzinfo=UTC)
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.SUCCEEDED, paid_at=paid_at)
    service = BillingService(FakeBillingRepository({payment_id: payment}))
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, admin)

    assert updated.status == PaymentStatusEnum.SUCCEEDED
    assert updated.paid_at == paid_at


@pytest.mark.asyncio
async def test_update_payment_status_allows_failed_to_pending_for_reconciliation() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.FAILED, paid_at=None)
    service = BillingService(FakeBillingRepository({payment_id: payment}))
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.PENDING, admin)

    assert updated.status == PaymentStatusEnum.PENDING
    assert updated.paid_at is None


@pytest.mark.asyncio
async def test_update_payment_status_rejects_invalid_transition() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service = BillingService(FakeBillingRepository({payment_id: payment}))
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.update_payment_status(payment_id, PaymentStatusEnum.REFUNDED, admin)


@pytest.mark.asyncio
async def test_update_payment_status_preserves_paid_at_on_refund() -> None:
    paid_at = datetime(2026, 2, 23, 9, 0, tzinfo=UTC)
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.SUCCEEDED, paid_at=paid_at)
    service = BillingService(FakeBillingRepository({payment_id: payment}))
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.REFUNDED, admin)

    assert updated.status == PaymentStatusEnum.REFUNDED
    assert updated.paid_at == paid_at


@pytest.mark.asyncio
async def test_update_payment_status_requires_admin() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service = BillingService(FakeBillingRepository({payment_id: payment}))
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, student)
