from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import NotificationStatusEnum, RoleEnum
from app.modules.admin.service import AdminService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


class FakeAdminRepository:
    def __init__(self, items: list[dict], total: int) -> None:
        self.items = items
        self.total = total
        self.calls: list[dict[str, object]] = []

    async def list_notifications(
        self,
        *,
        recipient_user_id,
        channel,
        status,
        template_key,
        created_from_utc,
        created_to_utc,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        self.calls.append(
            {
                "recipient_user_id": recipient_user_id,
                "channel": channel,
                "status": status,
                "template_key": template_key,
                "created_from_utc": created_from_utc,
                "created_to_utc": created_to_utc,
                "limit": limit,
                "offset": offset,
            },
        )
        return self.items, self.total


def make_actor(role: RoleEnum) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=SimpleNamespace(name=role))


def make_item() -> dict:
    return {
        "notification_id": uuid4(),
        "recipient_user_id": uuid4(),
        "channel": "email",
        "template_key": "booking_confirmed",
        "title": "Booking confirmed",
        "body": "Your booking is confirmed.",
        "status": NotificationStatusEnum.SENT,
        "sent_at_utc": datetime(2026, 3, 6, 12, 5, tzinfo=UTC),
        "created_at_utc": datetime(2026, 3, 6, 12, 0, tzinfo=UTC),
        "updated_at_utc": datetime(2026, 3, 6, 12, 5, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_admin_notifications_list_passes_filters_and_serializes_rows() -> None:
    item = make_item()
    repository = FakeAdminRepository(items=[item], total=1)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    recipient_user_id = uuid4()

    items, total = await service.list_notifications(
        admin,
        recipient_user_id=recipient_user_id,
        channel="email",
        status=NotificationStatusEnum.SENT,
        template_key="booking_confirmed",
        created_from_utc=datetime(2026, 3, 6, 0, 0, tzinfo=UTC),
        created_to_utc=datetime(2026, 3, 7, 0, 0, tzinfo=UTC),
        limit=20,
        offset=5,
    )

    assert total == 1
    assert items[0].notification_id == item["notification_id"]
    assert items[0].template_key == "booking_confirmed"
    assert repository.calls == [
        {
            "recipient_user_id": recipient_user_id,
            "channel": "email",
            "status": NotificationStatusEnum.SENT,
            "template_key": "booking_confirmed",
            "created_from_utc": datetime(2026, 3, 6, 0, 0, tzinfo=UTC),
            "created_to_utc": datetime(2026, 3, 7, 0, 0, tzinfo=UTC),
            "limit": 20,
            "offset": 5,
        },
    ]


@pytest.mark.asyncio
async def test_admin_notifications_list_normalizes_datetime_and_template_alias() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)
    tz_plus_3 = timezone(timedelta(hours=3))

    await service.list_notifications(
        admin,
        recipient_user_id=None,
        channel=None,
        status=None,
        template_key="booking_cancelled",
        created_from_utc=datetime(2026, 3, 7, 12, 0, tzinfo=tz_plus_3),
        created_to_utc=datetime(2026, 3, 8, 12, 0, tzinfo=tz_plus_3),
        limit=10,
        offset=0,
    )

    assert repository.calls == [
        {
            "recipient_user_id": None,
            "channel": None,
            "status": None,
            "template_key": "booking_canceled",
            "created_from_utc": datetime(2026, 3, 7, 9, 0, tzinfo=UTC),
            "created_to_utc": datetime(2026, 3, 8, 9, 0, tzinfo=UTC),
            "limit": 10,
            "offset": 0,
        },
    ]


@pytest.mark.asyncio
async def test_admin_notifications_list_requires_admin_role() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(UnauthorizedException):
        await service.list_notifications(
            teacher,
            recipient_user_id=None,
            channel=None,
            status=None,
            template_key=None,
            created_from_utc=None,
            created_to_utc=None,
            limit=10,
            offset=0,
        )

    assert repository.calls == []


@pytest.mark.asyncio
async def test_admin_notifications_list_validates_created_range() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.list_notifications(
            admin,
            recipient_user_id=None,
            channel=None,
            status=None,
            template_key=None,
            created_from_utc=datetime(2026, 3, 8, 10, 0, tzinfo=UTC),
            created_to_utc=datetime(2026, 3, 8, 9, 59, tzinfo=UTC),
            limit=10,
            offset=0,
        )


@pytest.mark.asyncio
async def test_admin_notifications_list_rejects_unknown_template_key() -> None:
    repository = FakeAdminRepository(items=[], total=0)
    service = AdminService(repository=repository)  # type: ignore[arg-type]
    admin = make_actor(RoleEnum.ADMIN)

    with pytest.raises(BusinessRuleException):
        await service.list_notifications(
            admin,
            recipient_user_id=None,
            channel=None,
            status=None,
            template_key="unknown_template",
            created_from_utc=None,
            created_to_utc=None,
            limit=10,
            offset=0,
        )
