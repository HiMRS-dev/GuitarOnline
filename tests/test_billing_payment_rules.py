from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

import app.modules.billing.service as billing_service_module
from app.core.enums import PackageStatusEnum, PaymentStatusEnum, RoleEnum
from app.modules.billing.providers import (
    PaymentProviderCreateResult,
    PaymentProviderRegistry,
    PaymentWebhookResult,
)
from app.modules.billing.schemas import PackageCreateAdmin, PaymentCreate
from app.modules.billing.service import BillingService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


@dataclass
class FakePayment:
    id: UUID
    status: PaymentStatusEnum
    package_id: UUID = field(default_factory=uuid4)
    amount: Decimal = Decimal("0")
    currency: str = "USD"
    external_reference: str | None = None
    paid_at: datetime | None = None


@dataclass
class FakePackage:
    id: UUID
    student_id: UUID
    status: PackageStatusEnum
    expires_at: datetime
    lessons_total: int
    lessons_left: int
    lessons_reserved: int = 0
    price_amount: Decimal | None = None
    price_currency: str | None = None


class FakeBillingRepository:
    def __init__(
        self,
        payments: dict[UUID, FakePayment] | None = None,
        packages: dict[UUID, FakePackage] | None = None,
    ) -> None:
        self._payments = payments or {}
        self._packages = packages or {}

    async def get_payment_by_id(self, payment_id: UUID) -> FakePayment | None:
        return self._payments.get(payment_id)

    async def get_payment_by_external_reference(
        self,
        external_reference: str,
    ) -> FakePayment | None:
        for payment in self._payments.values():
            if payment.external_reference == external_reference:
                return payment
        return None

    async def set_payment_status(
        self,
        payment: FakePayment,
        status: PaymentStatusEnum,
        paid_at: datetime | None,
    ) -> FakePayment:
        payment.status = status
        payment.paid_at = paid_at
        return payment

    async def get_package_by_id(self, package_id: UUID) -> FakePackage | None:
        return self._packages.get(package_id)

    async def create_package(
        self,
        student_id: UUID,
        lessons_total: int,
        expires_at: datetime,
        price_amount: Decimal | None = None,
        price_currency: str | None = None,
    ) -> FakePackage:
        package = FakePackage(
            id=uuid4(),
            student_id=student_id,
            status=PackageStatusEnum.ACTIVE,
            expires_at=expires_at,
            lessons_total=lessons_total,
            lessons_left=lessons_total,
            lessons_reserved=0,
            price_amount=price_amount,
            price_currency=price_currency,
        )
        self._packages[package.id] = package
        return package

    async def create_payment(
        self,
        package_id: UUID,
        amount: Decimal,
        currency: str,
        external_reference: str | None,
    ) -> FakePayment:
        payment = FakePayment(
            id=uuid4(),
            package_id=package_id,
            amount=amount,
            currency=currency.upper(),
            external_reference=external_reference,
            status=PaymentStatusEnum.PENDING,
        )
        self._payments[payment.id] = payment
        return payment

    async def set_package_status(
        self,
        package: FakePackage,
        status: PackageStatusEnum,
    ) -> FakePackage:
        package.status = status
        return package

    async def find_packages_to_expire(self, now: datetime) -> list[FakePackage]:
        return [
            package
            for package in self._packages.values()
            if package.status == PackageStatusEnum.ACTIVE and package.expires_at <= now
        ]


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


class FakePaymentProvider:
    def __init__(
        self,
        *,
        create_result: PaymentProviderCreateResult | None = None,
        webhook_result: PaymentWebhookResult | None = None,
        webhook_result_by_payload: dict[str, PaymentWebhookResult | None] | None = None,
    ) -> None:
        self._create_result = create_result or PaymentProviderCreateResult()
        self._webhook_result = webhook_result
        self._webhook_result_by_payload = webhook_result_by_payload or {}
        self.create_calls: list[dict[str, Any]] = []
        self.webhook_calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "manual_paid"

    async def create_payment(
        self,
        *,
        package_id: UUID,
        amount: str,
        currency: str,
        external_reference: str | None,
    ) -> PaymentProviderCreateResult:
        self.create_calls.append(
            {
                "package_id": package_id,
                "amount": amount,
                "currency": currency,
                "external_reference": external_reference,
            },
        )
        return self._create_result

    async def handle_webhook(self, payload: dict[str, Any]) -> PaymentWebhookResult | None:
        self.webhook_calls.append(payload)
        key = str(payload.get("event"))
        if key in self._webhook_result_by_payload:
            return self._webhook_result_by_payload[key]
        return self._webhook_result


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_service(
    payments: dict[UUID, FakePayment] | None = None,
    packages: dict[UUID, FakePackage] | None = None,
    provider_registry: PaymentProviderRegistry | None = None,
) -> tuple[BillingService, FakeAuditRepository]:
    audit_repo = FakeAuditRepository()
    service = BillingService(
        repository=FakeBillingRepository(payments=payments, packages=packages),
        audit_repository=audit_repo,
        provider_registry=provider_registry,
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
    service, audit_repo = make_service(payments={payment_id: payment})
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
    service, audit_repo = make_service(payments={payment_id: payment})
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
    service, _ = make_service(payments={payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.PENDING, admin)

    assert updated.status == PaymentStatusEnum.PENDING
    assert updated.paid_at is None


@pytest.mark.asyncio
async def test_update_payment_status_allows_failed_to_succeeded_with_paid_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 23, 10, 15, tzinfo=UTC)
    monkeypatch.setattr(billing_service_module, "utc_now", lambda: fixed_now)

    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.FAILED, paid_at=None)
    service, _ = make_service(payments={payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, admin)

    assert updated.status == PaymentStatusEnum.SUCCEEDED
    assert updated.paid_at == fixed_now


@pytest.mark.asyncio
async def test_update_payment_status_rejects_invalid_transition() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service, _ = make_service(payments={payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.update_payment_status(payment_id, PaymentStatusEnum.REFUNDED, admin)


@pytest.mark.asyncio
async def test_update_payment_status_preserves_paid_at_on_refund() -> None:
    paid_at = datetime(2026, 2, 23, 9, 0, tzinfo=UTC)
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.SUCCEEDED, paid_at=paid_at)
    service, _ = make_service(payments={payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    updated = await service.update_payment_status(payment_id, PaymentStatusEnum.REFUNDED, admin)

    assert updated.status == PaymentStatusEnum.REFUNDED
    assert updated.paid_at == paid_at


@pytest.mark.asyncio
async def test_update_payment_status_rejects_any_transition_from_refunded() -> None:
    paid_at = datetime(2026, 2, 23, 9, 0, tzinfo=UTC)
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.REFUNDED, paid_at=paid_at)
    service, _ = make_service(payments={payment_id: payment})
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.update_payment_status(payment_id, PaymentStatusEnum.PENDING, admin)


@pytest.mark.asyncio
async def test_update_payment_status_requires_admin() -> None:
    payment_id = uuid4()
    payment = FakePayment(id=payment_id, status=PaymentStatusEnum.PENDING, paid_at=None)
    service, _ = make_service(payments={payment_id: payment})
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.update_payment_status(payment_id, PaymentStatusEnum.SUCCEEDED, student)


@pytest.mark.asyncio
async def test_get_active_package_marks_expired_and_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 23, 11, 0, tzinfo=UTC)
    monkeypatch.setattr(billing_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    package_id = uuid4()
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now - timedelta(minutes=1),
        lessons_total=10,
        lessons_left=5,
    )
    service, audit_repo = make_service(packages={package_id: package})

    with pytest.raises(BusinessRuleException):
        await service.get_active_package(package_id=package_id, student_id=student_id)
    assert package.status == PackageStatusEnum.EXPIRED
    assert len(audit_repo.audit_logs) == 1
    assert len(audit_repo.outbox_events) == 1
    assert audit_repo.audit_logs[0]["payload"]["trigger"] == "active_package_check"
    assert audit_repo.outbox_events[0]["event_type"] == "billing.package.expired"


@pytest.mark.asyncio
async def test_create_payment_rejects_expired_package_and_marks_it_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 2, 23, 11, 30, tzinfo=UTC)
    monkeypatch.setattr(billing_service_module, "utc_now", lambda: fixed_now)

    student_id = uuid4()
    package_id = uuid4()
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=fixed_now - timedelta(minutes=5),
        lessons_total=10,
        lessons_left=10,
    )
    service, audit_repo = make_service(packages={package_id: package})
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.create_payment(
            PaymentCreate(
                package_id=package_id,
                amount=Decimal("99.00"),
                currency="usd",
                external_reference="pay-1",
            ),
            admin,
        )

    assert package.status == PackageStatusEnum.EXPIRED
    assert len(audit_repo.audit_logs) == 1
    assert len(audit_repo.outbox_events) == 1
    assert audit_repo.audit_logs[0]["payload"]["trigger"] == "payment_creation_check"
    assert audit_repo.outbox_events[0]["event_type"] == "billing.package.expired"


@pytest.mark.asyncio
async def test_create_payment_rejects_inactive_package_without_side_effects() -> None:
    student_id = uuid4()
    package_id = uuid4()
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.CANCELED,
        expires_at=datetime.now(UTC) + timedelta(days=5),
        lessons_total=10,
        lessons_left=10,
    )
    service, audit_repo = make_service(packages={package_id: package})
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.create_payment(
            PaymentCreate(
                package_id=package_id,
                amount=Decimal("49.00"),
                currency="usd",
                external_reference="pay-2",
            ),
            admin,
        )

    assert package.status == PackageStatusEnum.CANCELED
    assert len(audit_repo.audit_logs) == 0
    assert len(audit_repo.outbox_events) == 0


@pytest.mark.asyncio
async def test_create_admin_package_stores_price_snapshot_and_writes_admin_audit() -> None:
    admin = make_actor(RoleEnum.ADMIN)
    service, audit_repo = make_service()

    package = await service.create_admin_package(
        PackageCreateAdmin(
            student_id=uuid4(),
            lessons_total=12,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            price_amount=Decimal("149.00"),
            price_currency="usd",
        ),
        admin,
    )

    assert package.lessons_total == 12
    assert package.lessons_left == 12
    assert package.lessons_reserved == 0
    assert package.price_amount == Decimal("149.00")
    assert package.price_currency == "USD"
    assert len(audit_repo.audit_logs) == 1
    assert audit_repo.audit_logs[0]["action"] == "admin.package.create"
    assert audit_repo.audit_logs[0]["payload"]["price_amount"] == "149.00"
    assert audit_repo.audit_logs[0]["payload"]["price_currency"] == "USD"
    assert len(audit_repo.outbox_events) == 1
    assert audit_repo.outbox_events[0]["event_type"] == "billing.package.created"


@pytest.mark.asyncio
async def test_create_admin_package_rejects_past_expiration() -> None:
    admin = make_actor(RoleEnum.ADMIN)
    service, audit_repo = make_service()

    with pytest.raises(BusinessRuleException):
        await service.create_admin_package(
            PackageCreateAdmin(
                student_id=uuid4(),
                lessons_total=8,
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
                price_amount=Decimal("99.00"),
                price_currency="USD",
            ),
            admin,
        )

    assert len(audit_repo.audit_logs) == 0
    assert len(audit_repo.outbox_events) == 0


@pytest.mark.asyncio
async def test_create_admin_package_requires_admin() -> None:
    student = make_actor(RoleEnum.STUDENT)
    service, _ = make_service()

    with pytest.raises(UnauthorizedException):
        await service.create_admin_package(
            PackageCreateAdmin(
                student_id=uuid4(),
                lessons_total=8,
                expires_at=datetime.now(UTC) + timedelta(days=10),
                price_amount=Decimal("99.00"),
                price_currency="USD",
            ),
            student,
        )


@pytest.mark.asyncio
async def test_expire_packages_marks_active_overdue_packages() -> None:
    student_id = uuid4()
    admin = make_actor(RoleEnum.ADMIN)
    now = datetime.now(UTC)

    expired_candidate = FakePackage(
        id=uuid4(),
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=now - timedelta(hours=1),
        lessons_total=10,
        lessons_left=3,
    )
    active_future = FakePackage(
        id=uuid4(),
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=now + timedelta(hours=3),
        lessons_total=10,
        lessons_left=8,
    )
    already_expired = FakePackage(
        id=uuid4(),
        student_id=student_id,
        status=PackageStatusEnum.EXPIRED,
        expires_at=now - timedelta(days=1),
        lessons_total=10,
        lessons_left=0,
    )
    service, audit_repo = make_service(
        packages={
            expired_candidate.id: expired_candidate,
            active_future.id: active_future,
            already_expired.id: already_expired,
        },
    )

    updated = await service.expire_packages(admin)

    assert updated == 1
    assert expired_candidate.status == PackageStatusEnum.EXPIRED
    assert active_future.status == PackageStatusEnum.ACTIVE
    assert len(audit_repo.audit_logs) == 1
    assert audit_repo.audit_logs[0]["action"] == "billing.package.expire"
    assert len(audit_repo.outbox_events) == 1
    assert audit_repo.outbox_events[0]["event_type"] == "billing.package.expired"


@pytest.mark.asyncio
async def test_expire_packages_system_works_without_actor() -> None:
    student_id = uuid4()
    now = datetime.now(UTC)
    expired_candidate = FakePackage(
        id=uuid4(),
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=now - timedelta(hours=1),
        lessons_total=10,
        lessons_left=3,
    )
    service, audit_repo = make_service(packages={expired_candidate.id: expired_candidate})

    updated = await service.expire_packages_system(trigger="worker_expire_packages")

    assert updated == 1
    assert expired_candidate.status == PackageStatusEnum.EXPIRED
    assert len(audit_repo.audit_logs) == 1
    assert audit_repo.audit_logs[0]["actor_id"] is None
    assert audit_repo.audit_logs[0]["payload"]["trigger"] == "worker_expire_packages"
    assert len(audit_repo.outbox_events) == 1
    assert audit_repo.outbox_events[0]["event_type"] == "billing.package.expired"


@pytest.mark.asyncio
async def test_expire_packages_requires_admin() -> None:
    service, _ = make_service()
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.expire_packages(student)


@pytest.mark.asyncio
async def test_create_payment_routes_through_provider_abstraction() -> None:
    student_id = uuid4()
    package_id = uuid4()
    package = FakePackage(
        id=package_id,
        student_id=student_id,
        status=PackageStatusEnum.ACTIVE,
        expires_at=datetime.now(UTC) + timedelta(days=2),
        lessons_total=10,
        lessons_left=10,
    )
    provider = FakePaymentProvider(
        create_result=PaymentProviderCreateResult(
            status=PaymentStatusEnum.PENDING,
            external_reference="provider-ref-001",
            provider_payment_id="provider-pay-001",
        ),
    )
    service, audit_repo = make_service(
        packages={package_id: package},
        provider_registry=PaymentProviderRegistry(providers=[provider]),
    )
    admin = make_actor(RoleEnum.ADMIN)

    payment = await service.create_payment(
        PaymentCreate(
            package_id=package_id,
            amount=Decimal("59.00"),
            currency="usd",
            provider_name="manual_paid",
            external_reference=None,
        ),
        admin,
    )

    assert len(provider.create_calls) == 1
    assert provider.create_calls[0]["package_id"] == package_id
    assert payment.external_reference == "provider-ref-001"
    assert audit_repo.audit_logs[0]["payload"]["provider_name"] == "manual_paid"
    assert audit_repo.audit_logs[0]["payload"]["provider_payment_id"] == "provider-pay-001"


@pytest.mark.asyncio
async def test_handle_payment_webhook_updates_payment_status_by_provider_result() -> None:
    payment_id = uuid4()
    payment = FakePayment(
        id=payment_id,
        package_id=uuid4(),
        status=PaymentStatusEnum.PENDING,
        paid_at=None,
        external_reference="provider-ref-200",
    )
    provider = FakePaymentProvider(
        webhook_result_by_payload={
            "payment.succeeded": PaymentWebhookResult(
                external_reference="provider-ref-200",
                status=PaymentStatusEnum.SUCCEEDED,
            ),
        },
    )
    service, audit_repo = make_service(
        payments={payment_id: payment},
        provider_registry=PaymentProviderRegistry(providers=[provider]),
    )

    updated = await service.handle_payment_webhook(
        "manual_paid",
        {"event": "payment.succeeded"},
    )

    assert updated is not None
    assert updated.id == payment_id
    assert updated.status == PaymentStatusEnum.SUCCEEDED
    assert updated.paid_at is not None
    assert len(provider.webhook_calls) == 1
    assert audit_repo.audit_logs[0]["action"] == "billing.payment.webhook.update"
    assert audit_repo.audit_logs[0]["actor_id"] is None


@pytest.mark.asyncio
async def test_handle_payment_webhook_returns_none_when_provider_ignores_payload() -> None:
    provider = FakePaymentProvider(webhook_result=None)
    service, audit_repo = make_service(
        provider_registry=PaymentProviderRegistry(providers=[provider]),
    )

    result = await service.handle_payment_webhook(
        "manual_paid",
        {"event": "ignored"},
    )

    assert result is None
    assert len(provider.webhook_calls) == 1
    assert audit_repo.audit_logs == []
    assert audit_repo.outbox_events == []
