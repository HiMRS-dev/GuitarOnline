from __future__ import annotations

from datetime import UTC, datetime
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

    async def get_operations_overview(self, *, max_retries: int) -> dict:
        result = dict(self.snapshot)
        result["max_retries"] = max_retries
        return result

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
        "generated_at": datetime(2026, 2, 23, 19, 0, tzinfo=UTC),
        "max_retries": 5,
        "outbox_pending": 3,
        "outbox_failed_retryable": 2,
        "outbox_failed_dead_letter": 1,
        "notifications_failed": 4,
        "stale_booking_holds": 1,
        "overdue_active_packages": 2,
    }


@pytest.mark.asyncio
async def test_admin_operations_overview_returns_snapshot_and_traces_action() -> None:
    repository = FakeAdminRepository(snapshot=make_snapshot())
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    result = await service.get_operations_overview(admin, max_retries=7)

    assert result.max_retries == 7
    assert result.outbox_pending == 3
    assert result.overdue_active_packages == 2
    assert len(repository.actions) == 1
    assert repository.actions[0]["action"] == "admin.ops.view"
    assert repository.actions[0]["target_type"] == "operations_overview"
    assert repository.actions[0]["payload"]["max_retries"] == 7


@pytest.mark.asyncio
async def test_admin_operations_overview_requires_admin_role() -> None:
    repository = FakeAdminRepository(snapshot=make_snapshot())
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.get_operations_overview(teacher, max_retries=5)

    assert repository.actions == []
