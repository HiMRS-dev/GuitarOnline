"""Billing API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.modules.billing.schemas import (
    PackageCreate,
    PackageRead,
    PaymentCreate,
    PaymentRead,
    PaymentUpdateStatus,
)
from app.modules.billing.service import BillingService, get_billing_service
from app.modules.identity.service import get_current_user
from app.shared.pagination import Page, build_page, get_pagination_params

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/packages", response_model=PackageRead, status_code=status.HTTP_201_CREATED)
async def create_package(
    payload: PackageCreate,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(get_current_user),
) -> PackageRead:
    """Create a lesson package (admin only)."""
    package = await service.create_package(payload, current_user)
    return PackageRead.model_validate(package)


@router.get("/packages/students/{student_id}", response_model=Page[PackageRead])
async def list_student_packages(
    student_id: UUID,
    pagination=Depends(get_pagination_params),
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(get_current_user),
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


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreate,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(get_current_user),
) -> PaymentRead:
    """Create payment record."""
    payment = await service.create_payment(payload, current_user)
    return PaymentRead.model_validate(payment)


@router.patch("/payments/{payment_id}/status", response_model=PaymentRead)
async def update_payment_status(
    payment_id: UUID,
    payload: PaymentUpdateStatus,
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(get_current_user),
) -> PaymentRead:
    """Update payment status (admin)."""
    payment = await service.update_payment_status(payment_id, payload.status, current_user)
    return PaymentRead.model_validate(payment)


@router.post("/packages/expire", response_model=int)
async def expire_packages(
    service: BillingService = Depends(get_billing_service),
    current_user=Depends(get_current_user),
) -> int:
    """Expire outdated active lesson packages (admin)."""
    return await service.expire_packages(current_user)
