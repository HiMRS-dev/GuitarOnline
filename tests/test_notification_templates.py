from __future__ import annotations

import pytest

from app.core.enums import NotificationTemplateKeyEnum
from app.modules.notifications.templates import normalize_template_key, render_template


def test_template_key_normalization_supports_legacy_booking_cancelled_alias() -> None:
    normalized = normalize_template_key("booking_cancelled")
    assert normalized == NotificationTemplateKeyEnum.BOOKING_CANCELED


def test_render_template_returns_canonical_key_and_message() -> None:
    rendered = render_template(
        "lesson_reminder_24h",
        {
            "lesson_id": "lesson-123",
            "lesson_start_at_utc": "2026-03-10T10:00:00+00:00",
        },
    )

    assert rendered.template_key == NotificationTemplateKeyEnum.LESSON_REMINDER_24H
    assert rendered.title == "Lesson reminder"
    assert "lesson-123" in rendered.body
    assert "2026-03-10T10:00:00+00:00" in rendered.body


def test_template_key_normalization_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):
        normalize_template_key("unknown_template")
