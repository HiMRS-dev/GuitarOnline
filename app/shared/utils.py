"""Shared utility functions."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Normalize datetime to UTC timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
