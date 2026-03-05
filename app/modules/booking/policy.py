"""Booking policy helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.shared.utils import ensure_utc


def can_refund_by_policy(
    *,
    now_utc: datetime,
    slot_start_utc: datetime,
    refund_window_hours: int,
) -> bool:
    """Return True when cancellation is strictly earlier than refund window."""
    normalized_now = ensure_utc(now_utc)
    normalized_slot_start = ensure_utc(slot_start_utc)
    cutoff = timedelta(hours=refund_window_hours)
    return (normalized_slot_start - normalized_now) > cutoff
