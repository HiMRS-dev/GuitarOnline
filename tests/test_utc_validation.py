from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from app.modules.billing.schemas import PackageCreate
from app.modules.lessons.schemas import LessonCreate
from app.modules.scheduling.schemas import SlotCreate
from app.shared.utils import ensure_utc


def test_ensure_utc_sets_timezone_for_naive_datetime() -> None:
    naive = datetime(2026, 3, 4, 12, 0, 0)
    normalized = ensure_utc(naive)
    assert normalized.tzinfo == UTC
    assert normalized.hour == 12


def test_ensure_utc_converts_offset_datetime() -> None:
    source = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone(timedelta(hours=3)))
    normalized = ensure_utc(source)
    assert normalized.tzinfo == UTC
    assert normalized.hour == 9


def test_slot_create_normalizes_datetime_fields_to_utc() -> None:
    slot = SlotCreate(
        teacher_id=uuid4(),
        start_at=datetime(2026, 3, 6, 18, 0, tzinfo=timezone(timedelta(hours=5))),
        end_at=datetime(2026, 3, 6, 19, 0, tzinfo=timezone(timedelta(hours=5))),
    )
    assert slot.start_at.tzinfo == UTC
    assert slot.end_at.tzinfo == UTC
    assert slot.start_at.hour == 13
    assert slot.end_at.hour == 14


def test_package_create_normalizes_expires_at_to_utc() -> None:
    payload = PackageCreate(
        student_id=uuid4(),
        lessons_total=8,
        expires_at=datetime(2026, 5, 1, 1, 30, tzinfo=timezone(timedelta(hours=-2))),
    )
    assert payload.expires_at.tzinfo == UTC
    assert payload.expires_at.hour == 3


def test_lesson_create_normalizes_schedule_fields_to_utc() -> None:
    payload = LessonCreate(
        booking_id=uuid4(),
        student_id=uuid4(),
        teacher_id=uuid4(),
        scheduled_start_at=datetime(2026, 3, 10, 20, 0, tzinfo=timezone(timedelta(hours=9))),
        scheduled_end_at=datetime(2026, 3, 10, 21, 0, tzinfo=timezone(timedelta(hours=9))),
    )
    assert payload.scheduled_start_at.tzinfo == UTC
    assert payload.scheduled_end_at.tzinfo == UTC
    assert payload.scheduled_start_at.hour == 11
    assert payload.scheduled_end_at.hour == 12
