"""Billing repository layer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PackageStatusEnum, PaymentStatusEnum
from app.modules.billing.models import LessonPackage, Payment


class BillingRepository:
    """DB access methods for billing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_package(
        self,
        student_id: UUID,
        lessons_total: int,
        expires_at: datetime,
    ) -> LessonPackage:
        package = LessonPackage(
            student_id=student_id,
            lessons_total=lessons_total,
            lessons_left=lessons_total,
            expires_at=expires_at,
            status=PackageStatusEnum.ACTIVE,
        )
        self.session.add(package)
        await self.session.flush()
        return package

    async def get_package_by_id(self, package_id: UUID) -> LessonPackage | None:
        stmt = select(LessonPackage).where(LessonPackage.id == package_id)
        return await self.session.scalar(stmt)

    async def list_packages_by_student(
        self,
        student_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[LessonPackage], int]:
        base_stmt: Select[tuple[LessonPackage]] = select(LessonPackage).where(
            LessonPackage.student_id == student_id,
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self.session.scalar(count_stmt)) or 0)

        stmt = base_stmt.order_by(LessonPackage.created_at.desc()).limit(limit).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        return items, total

    async def create_payment(
        self,
        package_id: UUID,
        amount: Decimal,
        currency: str,
        external_reference: str | None,
    ) -> Payment:
        payment = Payment(
            package_id=package_id,
            amount=amount,
            currency=currency.upper(),
            external_reference=external_reference,
            status=PaymentStatusEnum.PENDING,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_payment_by_id(self, payment_id: UUID) -> Payment | None:
        stmt = select(Payment).where(Payment.id == payment_id)
        return await self.session.scalar(stmt)

    async def set_payment_status(
        self,
        payment: Payment,
        status: PaymentStatusEnum,
        paid_at: datetime | None,
    ) -> Payment:
        payment.status = status
        payment.paid_at = paid_at
        await self.session.flush()
        return payment

    async def consume_package_lesson(self, package: LessonPackage) -> None:
        package.lessons_left -= 1
        await self.session.flush()

    async def return_package_lesson(self, package: LessonPackage) -> None:
        package.lessons_left += 1
        await self.session.flush()

    async def find_packages_to_expire(self, now: datetime) -> list[LessonPackage]:
        stmt = select(LessonPackage).where(
            LessonPackage.status == PackageStatusEnum.ACTIVE,
            LessonPackage.expires_at <= now,
        )
        return (await self.session.scalars(stmt)).all()

    async def set_package_status(
        self,
        package: LessonPackage,
        status: PackageStatusEnum,
    ) -> LessonPackage:
        package.status = status
        await self.session.flush()
        return package
