"""Billing API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.enums import RoleEnum
from app.modules.billing.schemas import (
    PackageCreate,
    PackagePlanRead,
    PackagePurchaseRead,
    PackagePurchaseRequest,
    PackageRead,
    PaymentCreate,
    PaymentRead,
    PaymentUpdateStatus,
)
from app.modules.billing.service import BillingService, get_billing_service
from app.modules.identity.service import require_roles
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/billing", tags=["billing"])


def _serialize_plan(plan) -> PackagePlanRead:
    return PackagePlanRead(
        id=plan.id,
        title=plan.title,
        description=plan.description,
        lessons_total=plan.lessons_total,
        duration_days=plan.duration_days,
        price_amount=plan.price_amount,
        price_currency=plan.price_currency,
    )


@router.get("/plans", response_model=list[PackagePlanRead])
async def list_package_plans(
    service: BillingService = Depends(get_billing_service),
    _=Depends(require_roles(RoleEnum.ADMIN, RoleEnum.STUDENT)),
) -> list[PackagePlanRead]:
    """List package plans available for purchase."""
    return [_serialize_plan(plan) for plan in service.list_package_plans()]


@router.post("/packages", response_model=PackageRead, status_code=status.HTTP_201_CREATED)
async def create_package(
    payload: PackageCreate,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> PackageRead:
    """Create a lesson package (admin only)."""
    package = await service.create_package(payload, current_user)
    return PackageRead.model_validate(package)


@router.get("/packages/students/{student_id}", response_model=Page[PackageRead])
async def list_student_packages(
    student_id: UUID,
    pagination=Depends(get_pagination_params),
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN, RoleEnum.STUDENT)),
) -> Page[PackageRead]:
    """List packages for a specific student."""
    items, total = await service.list_student_packages(
        student_id=student_id,
        actor=current_user,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    serialized = [PackageRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)


@router.post(
    "/packages/purchase",
    response_model=PackagePurchaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def purchase_package(
    payload: PackagePurchaseRequest,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.STUDENT)),
) -> PackagePurchaseRead:
    """Purchase predefined package plan as student."""
    plan, package, payment = await service.purchase_package(
        plan_id=payload.plan_id,
        provider_name=payload.provider_name,
        actor=current_user,
    )
    return PackagePurchaseRead(
        plan=_serialize_plan(plan),
        package=PackageRead.model_validate(package),
        payment=PaymentRead.model_validate(payment),
    )


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreate,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN, RoleEnum.STUDENT)),
) -> PaymentRead:
    """Create payment record."""
    payment = await service.create_payment(payload, current_user)
    return PaymentRead.model_validate(payment)


@router.get("/payments/students/{student_id}", response_model=Page[PaymentRead])
async def list_student_payments(
    student_id: UUID,
    pagination=Depends(get_pagination_params),
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN, RoleEnum.STUDENT)),
) -> Page[PaymentRead]:
    """List payment history for a specific student."""
    items, total = await service.list_student_payments(
        student_id=student_id,
        actor=current_user,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    serialized = [PaymentRead.model_validate(item) for item in items]
    return build_page(serialized, total, pagination)


@router.patch("/payments/{payment_id}/status", response_model=PaymentRead)
async def update_payment_status(
    payment_id: UUID,
    payload: PaymentUpdateStatus,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> PaymentRead:
    """Update payment status (admin)."""
    payment = await service.update_payment_status(payment_id, payload.status, current_user)
    return PaymentRead.model_validate(payment)


@router.post("/packages/expire", response_model=int)
async def expire_packages(
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(require_roles(RoleEnum.ADMIN)),
) -> int:
    """Expire outdated active lesson packages (admin)."""
    return await service.expire_packages(current_user)
