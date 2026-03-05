"""Payment provider abstraction for billing domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.core.enums import PaymentStatusEnum
from app.shared.exceptions import BusinessRuleException
from app.shared.utils import ensure_utc


@dataclass(slots=True, frozen=True)
class PaymentProviderCreateResult:
    """Result of provider payment creation intent."""

    status: PaymentStatusEnum = PaymentStatusEnum.PENDING
    external_reference: str | None = None
    provider_payment_id: str | None = None
    paid_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class PaymentWebhookResult:
    """Resolved status update produced by provider webhook."""

    payment_id: UUID | None = None
    external_reference: str | None = None
    provider_payment_id: str | None = None
    status: PaymentStatusEnum | None = None
    paid_at: datetime | None = None


class PaymentProvider(Protocol):
    """Provider contract for payment creation and webhook handling."""

    @property
    def name(self) -> str:
        """Stable provider identity token."""

    async def create_payment(
        self,
        *,
        package_id: UUID,
        amount: str,
        currency: str,
        external_reference: str | None,
    ) -> PaymentProviderCreateResult:
        """Create provider-side payment intent or manual marker."""

    async def handle_webhook(self, payload: dict[str, Any]) -> PaymentWebhookResult | None:
        """Parse provider webhook payload to internal status change."""


class ManualPaidPaymentProvider:
    """Manual provider used in v1 while no external gateway is integrated."""

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
        _ = package_id, amount, currency
        return PaymentProviderCreateResult(
            status=PaymentStatusEnum.PENDING,
            external_reference=external_reference,
            provider_payment_id=external_reference,
            paid_at=None,
        )

    async def handle_webhook(self, payload: dict[str, Any]) -> PaymentWebhookResult | None:
        payment_id_raw = payload.get("payment_id")
        external_reference = payload.get("external_reference")
        provider_payment_id = payload.get("provider_payment_id")
        status_raw = payload.get("status")
        if status_raw is None:
            return None

        try:
            status = PaymentStatusEnum(str(status_raw).strip().lower())
        except ValueError as exc:
            raise BusinessRuleException("Unsupported payment status in webhook payload") from exc

        paid_at_raw = payload.get("paid_at")
        paid_at: datetime | None = None
        if paid_at_raw is not None:
            if not isinstance(paid_at_raw, str):
                raise BusinessRuleException("Webhook paid_at must be ISO string")
            try:
                paid_at = ensure_utc(datetime.fromisoformat(paid_at_raw))
            except ValueError as exc:
                raise BusinessRuleException("Webhook paid_at is not valid ISO datetime") from exc

        payment_id: UUID | None = None
        if payment_id_raw is not None:
            try:
                payment_id = UUID(str(payment_id_raw))
            except ValueError as exc:
                raise BusinessRuleException("Webhook payment_id must be valid UUID") from exc

        return PaymentWebhookResult(
            payment_id=payment_id,
            external_reference=str(external_reference) if external_reference else None,
            provider_payment_id=str(provider_payment_id) if provider_payment_id else None,
            status=status,
            paid_at=paid_at,
        )


class PaymentProviderRegistry:
    """In-memory provider registry for billing service."""

    def __init__(
        self,
        providers: list[PaymentProvider] | None = None,
        *,
        default_provider_name: str = "manual_paid",
    ) -> None:
        provider_items = providers or [ManualPaidPaymentProvider()]
        self._providers = {provider.name: provider for provider in provider_items}
        self._default_provider_name = default_provider_name
        if self._default_provider_name not in self._providers:
            raise ValueError(f"Default payment provider is not configured: {default_provider_name}")

    def resolve(self, provider_name: str | None) -> PaymentProvider:
        normalized_name = (
            provider_name.strip().lower()
            if isinstance(provider_name, str) and provider_name.strip()
            else self._default_provider_name
        )
        provider = self._providers.get(normalized_name)
        if provider is None:
            raise BusinessRuleException(f"Unsupported payment provider: {normalized_name}")
        return provider
