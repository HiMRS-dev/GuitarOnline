from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import RoleEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


class FakeAdminRepository:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot
        self.actions: list[dict] = []
        self.calls: list[dict] = []

    async def get_kpi_sales(
        self,
        *,
        from_utc: datetime,
        to_utc: datetime,
    ) -> dict:
        self.calls.append({"from_utc": from_utc, "to_utc": to_utc})
        return dict(self.snapshot)

    async def create_action(
        self,
        admin_id,
        action: str,
        target_type: str,
        target_id: str | None,
        payload: dict,
    ) -> None:
        self.actions.append(
            {
                "admin_id": admin_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "payload": payload,
            },
        )


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_snapshot() -> dict:
    return {
        "generated_at": datetime(2026, 3, 6, 8, 0, tzinfo=UTC),
        "from_utc": datetime(2026, 3, 1, 0, 0, tzinfo=UTC),
        "to_utc": datetime(2026, 3, 5, 23, 59, tzinfo=UTC),
        "payments_succeeded_count": 7,
        "payments_refunded_count": 2,
        "payments_succeeded_amount": Decimal("700.00"),
        "payments_refunded_amount": Decimal("100.00"),
        "payments_net_amount": Decimal("600.00"),
        "packages_created_total": 10,
        "packages_created_paid": 6,
        "packages_created_unpaid": 4,
        "packages_created_paid_conversion_rate": Decimal("0.6"),
    }


@pytest.mark.asyncio
async def test_admin_kpi_sales_returns_snapshot_and_writes_action() -> None:
    repository = FakeAdminRepository(snapshot=make_snapshot())
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    from_utc = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
    to_utc = datetime(2026, 3, 5, 23, 59, tzinfo=UTC)

    result = await service.get_kpi_sales(
        admin,
        from_utc=from_utc,
        to_utc=to_utc,
    )

    assert result.payments_succeeded_count == 7
    assert result.payments_net_amount == Decimal("600.00")
    assert result.packages_created_total == 10
    assert result.packages_created_paid == 6
    assert result.packages_created_unpaid == 4
    assert len(repository.calls) == 1
    assert repository.calls[0]["from_utc"] == from_utc
    assert repository.calls[0]["to_utc"] == to_utc
    assert len(repository.actions) == 1
    assert repository.actions[0]["action"] == "admin.kpi.sales.view"
    assert repository.actions[0]["target_type"] == "kpi_sales"


@pytest.mark.asyncio
async def test_admin_kpi_sales_requires_admin_role() -> None:
    repository = FakeAdminRepository(snapshot=make_snapshot())
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.get_kpi_sales(
            student,
            from_utc=datetime(2026, 3, 1, 0, 0, tzinfo=UTC),
            to_utc=datetime(2026, 3, 5, 23, 59, tzinfo=UTC),
        )

    assert repository.calls == []
    assert repository.actions == []


@pytest.mark.asyncio
async def test_admin_kpi_sales_rejects_invalid_range() -> None:
    repository = FakeAdminRepository(snapshot=make_snapshot())
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.get_kpi_sales(
            admin,
            from_utc=datetime(2026, 3, 6, 0, 0, tzinfo=UTC),
            to_utc=datetime(2026, 3, 1, 0, 0, tzinfo=UTC),
        )

    assert repository.calls == []
    assert repository.actions == []
