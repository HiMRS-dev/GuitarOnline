"""Shared utility functions."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return aware UTC datetime."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Normalize datetime to UTC timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
