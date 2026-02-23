from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import app.modules.billing.service as billing_service_module
from app.core.enums import PackageStatusEnum, PaymentStatusEnum, RoleEnum
from app.modules.billing.schemas import PaymentCreate
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


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_service(
    payments: dict[UUID, FakePayment] | None = None,
    packages: dict[UUID, FakePackage] | None = None,
) -> tuple[BillingService, FakeAuditRepository]:
    audit_repo = FakeAuditRepository()
    service = BillingService(
        repository=FakeBillingRepository(payments=payments, packages=packages),
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
async def test_expire_packages_requires_admin() -> None:
    service, _ = make_service()
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.expire_packages(student)
