from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import RoleEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import UnauthorizedException


class FakeAdminRepository:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot
        self.actions: list[dict] = []

    async def get_kpi_overview(self) -> dict:
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
        "generated_at": datetime(2026, 2, 23, 18, 0, tzinfo=UTC),
        "users_total": 12,
        "users_students": 8,
        "users_teachers": 3,
        "users_admins": 1,
        "bookings_total": 20,
        "bookings_hold": 1,
        "bookings_confirmed": 12,
        "bookings_canceled": 5,
        "bookings_expired": 2,
        "lessons_total": 10,
        "lessons_scheduled": 6,
        "lessons_completed": 3,
        "lessons_canceled": 1,
        "payments_total": 9,
        "payments_pending": 2,
        "payments_succeeded": 5,
        "payments_failed": 1,
        "payments_refunded": 1,
        "payments_succeeded_amount": Decimal("450.00"),
        "payments_refunded_amount": Decimal("50.00"),
        "payments_net_amount": Decimal("400.00"),
        "packages_total": 7,
        "packages_active": 4,
        "packages_expired": 2,
        "packages_canceled": 1,
    }


@pytest.mark.asyncio
async def test_admin_kpi_overview_returns_snapshot_and_traces_action() -> None:
    repository = FakeAdminRepository(snapshot=make_snapshot())
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.get_kpi_overview(admin)

    assert result.users_total == 12
    assert result.bookings_confirmed == 12
    assert result.payments_net_amount == Decimal("400.00")
    assert len(repository.actions) == 1
    assert repository.actions[0]["action"] == "admin.kpi.view"
    assert repository.actions[0]["target_type"] == "kpi_overview"
    assert repository.actions[0]["payload"]["generated_at"] == result.generated_at.isoformat()


@pytest.mark.asyncio
async def test_admin_kpi_overview_requires_admin_role() -> None:
    repository = FakeAdminRepository(snapshot=make_snapshot())
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException):
        await service.get_kpi_overview(student)

    assert repository.actions == []
