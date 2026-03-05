"""Billing business logic layer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import PackageStatusEnum, PaymentStatusEnum, RoleEnum
from app.modules.audit.repository import AuditRepository
from app.modules.billing.models import LessonPackage, Payment
from app.modules.billing.providers import PaymentProviderRegistry
from app.modules.billing.repository import BillingRepository
from app.modules.billing.schemas import PackageCreate, PackageCreateAdmin, PaymentCreate
from app.modules.identity.models import User
from app.shared.exceptions import BusinessRuleException, NotFoundException, UnauthorizedException
from app.shared.utils import ensure_utc, utc_now


class BillingService:
    """Billing domain service."""

    def __init__(
        self,
        repository: BillingRepository,
        audit_repository: AuditRepository,
        provider_registry: PaymentProviderRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.audit_repository = audit_repository
        self.provider_registry = provider_registry or PaymentProviderRegistry()

    @staticmethod
    def _available_lessons(package: LessonPackage) -> int:
        return package.lessons_left - package.lessons_reserved

    async def _expire_package(
        self,
        package: LessonPackage,
        *,
        actor_id: UUID | None,
        now: datetime,
        trigger: str,
    ) -> None:
        """Expire package and emit audit/outbox once."""
        if package.status == PackageStatusEnum.EXPIRED:
            return

        await self.repository.set_package_status(package, PackageStatusEnum.EXPIRED)
        await self.audit_repository.create_audit_log(
            actor_id=actor_id,
            action="billing.package.expire",
            entity_type="lesson_package",
            entity_id=str(package.id),
            payload={
                "student_id": str(package.student_id),
                "expired_at": now.isoformat(),
                "trigger": trigger,
            },
        )
        await self.audit_repository.create_outbox_event(
            aggregate_type="billing",
            aggregate_id=str(package.id),
            event_type="billing.package.expired",
            payload={
                "package_id": str(package.id),
                "student_id": str(package.student_id),
                "trigger": trigger,
            },
        )

    @staticmethod
    def _allowed_payment_transitions() -> dict[PaymentStatusEnum, set[PaymentStatusEnum]]:
        return {
            PaymentStatusEnum.PENDING: {PaymentStatusEnum.SUCCEEDED, PaymentStatusEnum.FAILED},
            PaymentStatusEnum.FAILED: {PaymentStatusEnum.PENDING, PaymentStatusEnum.SUCCEEDED},
            PaymentStatusEnum.SUCCEEDED: {PaymentStatusEnum.REFUNDED},
            PaymentStatusEnum.REFUNDED: set(),
        }

    @staticmethod
    def _resolve_paid_at_for_status(
        payment: Payment,
        *,
        status: PaymentStatusEnum,
        paid_at: datetime | None,
    ) -> datetime | None:
        if status == PaymentStatusEnum.SUCCEEDED:
            return ensure_utc(paid_at) if paid_at is not None else payment.paid_at or utc_now()
        if status == PaymentStatusEnum.REFUNDED:
            return payment.paid_at
        return None

    async def _set_payment_status(
        self,
        *,
        payment: Payment,
        status: PaymentStatusEnum,
        actor_id: UUID | None,
        action: str,
        paid_at: datetime | None = None,
        payload_extra: dict[str, Any] | None = None,
    ) -> Payment:
        previous_status = payment.status
        if status == previous_status:
            return payment

        allowed_transitions = self._allowed_payment_transitions()
        if status not in allowed_transitions[previous_status]:
            raise BusinessRuleException(
                f"Invalid payment status transition: {previous_status} -> {status}",
            )

        resolved_paid_at = self._resolve_paid_at_for_status(
            payment,
            status=status,
            paid_at=paid_at,
        )
        payment = await self.repository.set_payment_status(payment, status, resolved_paid_at)

        payload: dict[str, Any] = {
            "from_status": str(previous_status),
            "to_status": str(status),
            "paid_at": payment.paid_at.isoformat() if payment.paid_at is not None else None,
        }
        if payload_extra:
            payload.update(payload_extra)

        await self.audit_repository.create_audit_log(
            actor_id=actor_id,
            action=action,
            entity_type="payment",
            entity_id=str(payment.id),
            payload=payload,
        )
        await self.audit_repository.create_outbox_event(
            aggregate_type="billing",
            aggregate_id=str(payment.id),
            event_type="billing.payment.status.updated",
            payload={
                "payment_id": str(payment.id),
                "from_status": str(previous_status),
                "to_status": str(status),
            },
        )
        return payment

    async def create_package(self, payload: PackageCreate, actor: User) -> LessonPackage:
        """Create lessons package for a student."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create lesson packages")

        expires_at = ensure_utc(payload.expires_at)
        if expires_at <= utc_now():
            raise BusinessRuleException("Package expiration must be in the future")

        package = await self.repository.create_package(
            payload.student_id,
            payload.lessons_total,
            expires_at,
            price_amount=None,
            price_currency=None,
        )
        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="billing.package.create",
            entity_type="lesson_package",
            entity_id=str(package.id),
            payload={
                "student_id": str(package.student_id),
                "lessons_total": package.lessons_total,
                "expires_at": package.expires_at.isoformat(),
            },
        )
        await self.audit_repository.create_outbox_event(
            aggregate_type="billing",
            aggregate_id=str(package.id),
            event_type="billing.package.created",
            payload={
                "package_id": str(package.id),
                "student_id": str(package.student_id),
                "lessons_total": package.lessons_total,
            },
        )
        return package

    async def create_admin_package(
        self,
        payload: PackageCreateAdmin,
        actor: User,
    ) -> LessonPackage:
        """Create admin package with price snapshot and admin audit action."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can create lesson packages")

        expires_at = ensure_utc(payload.expires_at)
        if expires_at <= utc_now():
            raise BusinessRuleException("Package expiration must be in the future")

        price_currency = payload.price_currency.upper()
        package = await self.repository.create_package(
            payload.student_id,
            payload.lessons_total,
            expires_at,
            price_amount=Decimal(payload.price_amount),
            price_currency=price_currency,
        )
        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="admin.package.create",
            entity_type="lesson_package",
            entity_id=str(package.id),
            payload={
                "student_id": str(package.student_id),
                "lessons_total": package.lessons_total,
                "price_amount": str(package.price_amount),
                "price_currency": package.price_currency,
                "expires_at": package.expires_at.isoformat(),
            },
        )
        await self.audit_repository.create_outbox_event(
            aggregate_type="billing",
            aggregate_id=str(package.id),
            event_type="billing.package.created",
            payload={
                "package_id": str(package.id),
                "student_id": str(package.student_id),
                "lessons_total": package.lessons_total,
                "price_amount": str(package.price_amount),
                "price_currency": package.price_currency,
            },
        )
        return package

    async def list_student_packages(
        self,
        student_id: UUID,
        actor: User,
        limit: int,
        offset: int,
    ) -> tuple[list[LessonPackage], int]:
        """List packages for student."""
        if actor.role.name != RoleEnum.ADMIN and actor.id != student_id:
            raise UnauthorizedException("Access denied")
        return await self.repository.list_packages_by_student(
            student_id=student_id,
            limit=limit,
            offset=offset,
        )

    async def get_active_package(self, package_id: UUID, student_id: UUID) -> LessonPackage:
        """Return active package with all business checks."""
        package = await self.repository.get_package_by_id(package_id)
        if package is None:
            raise NotFoundException("Package not found")
        if package.student_id != student_id:
            raise UnauthorizedException("Package does not belong to current student")

        now = utc_now()
        is_expired = package.expires_at <= now
        if package.status == PackageStatusEnum.ACTIVE and is_expired:
            await self._expire_package(
                package,
                actor_id=None,
                now=now,
                trigger="active_package_check",
            )

        if is_expired:
            raise BusinessRuleException("Package is expired")

        if package.status != PackageStatusEnum.ACTIVE:
            raise BusinessRuleException("Package is not active")

        if self._available_lessons(package) <= 0:
            raise BusinessRuleException("No lessons left in package")

        return package

    async def consume_lesson(self, package: LessonPackage) -> None:
        """Consume one lesson from package."""
        if package.lessons_left <= 0:
            raise BusinessRuleException("No lessons left")
        if package.lessons_reserved <= 0:
            raise BusinessRuleException("No reserved lessons to consume")
        await self.repository.consume_reserved_package_lesson(package)

    async def return_lesson(self, package: LessonPackage) -> None:
        """Release one reserved lesson back to available capacity."""
        if package.lessons_reserved <= 0:
            return
        await self.repository.release_package_reservation(package)

    async def expire_packages(self, actor: User) -> int:
        """Expire all active packages that are past expiration timestamp."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can expire packages")

        return await self.expire_packages_system(actor_id=actor.id, trigger="admin_expire_packages")

    async def expire_packages_system(
        self,
        *,
        actor_id: UUID | None = None,
        trigger: str = "system_expire_packages",
    ) -> int:
        """Expire all active packages past expiration timestamp without user-token context."""
        now = utc_now()
        packages = await self.repository.find_packages_to_expire(now)
        for package in packages:
            await self._expire_package(
                package,
                actor_id=actor_id,
                now=now,
                trigger=trigger,
            )
        return len(packages)

    async def create_payment(self, payload: PaymentCreate, actor: User) -> Payment:
        """Create payment record."""
        if actor.role.name not in (RoleEnum.ADMIN, RoleEnum.STUDENT):
            raise UnauthorizedException("Role is not allowed for payments")

        package = await self.repository.get_package_by_id(payload.package_id)
        if package is None:
            raise NotFoundException("Package not found")

        if actor.role.name == RoleEnum.STUDENT and package.student_id != actor.id:
            raise UnauthorizedException("Students can pay only their packages")

        now = utc_now()
        is_expired = package.expires_at <= now
        if package.status == PackageStatusEnum.ACTIVE and is_expired:
            await self._expire_package(
                package,
                actor_id=actor.id,
                now=now,
                trigger="payment_creation_check",
            )
        if is_expired:
            raise BusinessRuleException("Package is expired")
        if package.status != PackageStatusEnum.ACTIVE:
            raise BusinessRuleException("Package is not active")

        provider = self.provider_registry.resolve(payload.provider_name)
        provider_create_result = await provider.create_payment(
            package_id=package.id,
            amount=str(payload.amount),
            currency=payload.currency,
            external_reference=payload.external_reference,
        )

        payment = await self.repository.create_payment(
            package_id=payload.package_id,
            amount=Decimal(payload.amount),
            currency=payload.currency,
            provider_name=provider.name,
            provider_payment_id=provider_create_result.provider_payment_id,
            external_reference=(
                provider_create_result.external_reference or payload.external_reference
            ),
        )
        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="billing.payment.create",
            entity_type="payment",
            entity_id=str(payment.id),
            payload={
                "package_id": str(payment.package_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "external_reference": payment.external_reference,
                "provider_name": payment.provider_name,
                "provider_payment_id": payment.provider_payment_id,
            },
        )
        await self.audit_repository.create_outbox_event(
            aggregate_type="billing",
            aggregate_id=str(payment.id),
            event_type="billing.payment.created",
            payload={
                "payment_id": str(payment.id),
                "package_id": str(payment.package_id),
                "status": str(payment.status),
                "provider_name": payment.provider_name,
            },
        )
        if provider_create_result.status != payment.status:
            payment = await self._set_payment_status(
                payment=payment,
                status=provider_create_result.status,
                actor_id=actor.id,
                action="billing.payment.provider.status.sync",
                paid_at=provider_create_result.paid_at,
                payload_extra={"provider_name": provider.name},
            )
        return payment

    async def update_payment_status(
        self,
        payment_id: UUID,
        status: PaymentStatusEnum,
        actor: User,
    ) -> Payment:
        """Update payment status (admin only)."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can update payment status")

        payment = await self.repository.get_payment_by_id(payment_id)
        if payment is None:
            raise NotFoundException("Payment not found")

        return await self._set_payment_status(
            payment=payment,
            status=status,
            actor_id=actor.id,
            action="billing.payment.status.update",
        )

    async def handle_payment_webhook(
        self,
        provider_name: str,
        payload: dict[str, Any],
    ) -> Payment | None:
        """Resolve and apply provider webhook status update."""
        provider = self.provider_registry.resolve(provider_name)
        webhook_result = await provider.handle_webhook(payload)
        if webhook_result is None or webhook_result.status is None:
            return None

        payment: Payment | None = None
        if webhook_result.payment_id is not None:
            payment = await self.repository.get_payment_by_id(webhook_result.payment_id)
        if payment is None and webhook_result.external_reference:
            payment = await self.repository.get_payment_by_external_reference(
                webhook_result.external_reference,
            )
        if payment is None and webhook_result.provider_payment_id:
            payment = await self.repository.get_payment_by_provider_payment_id(
                webhook_result.provider_payment_id,
            )
        if payment is None:
            raise NotFoundException("Payment not found for webhook payload")

        return await self._set_payment_status(
            payment=payment,
            status=webhook_result.status,
            actor_id=None,
            action="billing.payment.webhook.update",
            paid_at=webhook_result.paid_at,
            payload_extra={"provider_name": provider.name},
        )


async def get_billing_service(session: AsyncSession = Depends(get_db_session)) -> BillingService:
    """Dependency provider for billing service."""
    return BillingService(
        repository=BillingRepository(session),
        audit_repository=AuditRepository(session),
    )
