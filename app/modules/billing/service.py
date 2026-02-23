"""Billing business logic layer."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.enums import PackageStatusEnum, PaymentStatusEnum, RoleEnum
from app.modules.audit.repository import AuditRepository
from app.modules.billing.models import LessonPackage, Payment
from app.modules.billing.repository import BillingRepository
from app.modules.billing.schemas import PackageCreate, PaymentCreate
from app.modules.identity.models import User
from app.shared.exceptions import BusinessRuleException, NotFoundException, UnauthorizedException
from app.shared.utils import ensure_utc, utc_now


class BillingService:
    """Billing domain service."""

    def __init__(
        self,
        repository: BillingRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.repository = repository
        self.audit_repository = audit_repository

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

        if package.expires_at <= utc_now():
            if package.status != PackageStatusEnum.EXPIRED:
                await self.repository.set_package_status(package, PackageStatusEnum.EXPIRED)
            raise BusinessRuleException("Package is expired")

        if package.status != PackageStatusEnum.ACTIVE:
            raise BusinessRuleException("Package is not active")

        if package.lessons_left <= 0:
            raise BusinessRuleException("No lessons left in package")

        return package

    async def consume_lesson(self, package: LessonPackage) -> None:
        """Consume one lesson from package."""
        if package.lessons_left <= 0:
            raise BusinessRuleException("No lessons left")
        await self.repository.consume_package_lesson(package)

    async def return_lesson(self, package: LessonPackage) -> None:
        """Return one lesson back to package."""
        if package.lessons_left >= package.lessons_total:
            return
        await self.repository.return_package_lesson(package)

    async def expire_packages(self, actor: User) -> int:
        """Expire all active packages that are past expiration timestamp."""
        if actor.role.name != RoleEnum.ADMIN:
            raise UnauthorizedException("Only admin can expire packages")

        now = utc_now()
        packages = await self.repository.find_packages_to_expire(now)
        for package in packages:
            await self.repository.set_package_status(package, PackageStatusEnum.EXPIRED)
            await self.audit_repository.create_audit_log(
                actor_id=actor.id,
                action="billing.package.expire",
                entity_type="lesson_package",
                entity_id=str(package.id),
                payload={
                    "student_id": str(package.student_id),
                    "expired_at": now.isoformat(),
                },
            )
            await self.audit_repository.create_outbox_event(
                aggregate_type="billing",
                aggregate_id=str(package.id),
                event_type="billing.package.expired",
                payload={
                    "package_id": str(package.id),
                    "student_id": str(package.student_id),
                },
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

        payment = await self.repository.create_payment(
            package_id=payload.package_id,
            amount=Decimal(payload.amount),
            currency=payload.currency,
            external_reference=payload.external_reference,
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
            },
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

        if payment.status == status:
            return payment
        previous_status = payment.status

        allowed_transitions: dict[PaymentStatusEnum, set[PaymentStatusEnum]] = {
            PaymentStatusEnum.PENDING: {PaymentStatusEnum.SUCCEEDED, PaymentStatusEnum.FAILED},
            PaymentStatusEnum.FAILED: {PaymentStatusEnum.PENDING, PaymentStatusEnum.SUCCEEDED},
            PaymentStatusEnum.SUCCEEDED: {PaymentStatusEnum.REFUNDED},
            PaymentStatusEnum.REFUNDED: set(),
        }
        if status not in allowed_transitions[payment.status]:
            raise BusinessRuleException(
                f"Invalid payment status transition: {payment.status} -> {status}",
            )

        if status == PaymentStatusEnum.SUCCEEDED:
            paid_at = payment.paid_at or utc_now()
        elif status == PaymentStatusEnum.REFUNDED:
            paid_at = payment.paid_at
        else:
            paid_at = None

        payment = await self.repository.set_payment_status(payment, status, paid_at)
        await self.audit_repository.create_audit_log(
            actor_id=actor.id,
            action="billing.payment.status.update",
            entity_type="payment",
            entity_id=str(payment.id),
            payload={
                "from_status": str(previous_status),
                "to_status": str(status),
                "paid_at": payment.paid_at.isoformat() if payment.paid_at is not None else None,
            },
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


async def get_billing_service(session: AsyncSession = Depends(get_db_session)) -> BillingService:
    """Dependency provider for billing service."""
    return BillingService(
        repository=BillingRepository(session),
        audit_repository=AuditRepository(session),
    )
