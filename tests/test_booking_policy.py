from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.booking.policy import can_refund_by_policy


@pytest.mark.parametrize(
    ("offset_seconds", "expect_refund"),
    [
        (24 * 3600 - 1, False),  # 23:59:59
        (24 * 3600, False),  # 24:00:00
        (24 * 3600 + 1, True),  # 24:00:01
    ],
)
def test_can_refund_by_policy_boundaries(offset_seconds: int, expect_refund: bool) -> None:
    now = datetime(2026, 3, 5, 12, 0, tzinfo=UTC)
    slot_start = now + timedelta(seconds=offset_seconds)

    result = can_refund_by_policy(
        now_utc=now,
        slot_start_utc=slot_start,
        refund_window_hours=24,
    )

    assert result is expect_refund
