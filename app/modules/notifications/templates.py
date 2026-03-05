"""Notification templates registry and render helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.enums import NotificationTemplateKeyEnum

LEGACY_TEMPLATE_KEY_ALIASES: dict[str, NotificationTemplateKeyEnum] = {
    "booking_cancelled": NotificationTemplateKeyEnum.BOOKING_CANCELED,
}


@dataclass(frozen=True, slots=True)
class NotificationTemplate:
    """Template metadata and text rendering."""

    key: NotificationTemplateKeyEnum
    title: str

    def render_body(self, payload: dict[str, Any]) -> str:
        if self.key == NotificationTemplateKeyEnum.BOOKING_CONFIRMED:
            booking_id = payload.get("booking_id", "unknown")
            return f"Your booking {booking_id} has been confirmed."
        if self.key == NotificationTemplateKeyEnum.BOOKING_CANCELED:
            booking_id = payload.get("booking_id", "unknown")
            return f"Your booking {booking_id} has been canceled."

        lesson_id = payload.get("lesson_id", "unknown")
        lesson_start_at = payload.get("lesson_start_at_utc")
        if lesson_start_at:
            return f"Reminder: lesson {lesson_id} starts at {lesson_start_at}."
        return f"Reminder: lesson {lesson_id} starts in less than 24 hours."


@dataclass(frozen=True, slots=True)
class RenderedNotificationTemplate:
    """Rendered message payload from template key and context."""

    template_key: NotificationTemplateKeyEnum
    title: str
    body: str


TEMPLATE_REGISTRY: dict[NotificationTemplateKeyEnum, NotificationTemplate] = {
    NotificationTemplateKeyEnum.BOOKING_CONFIRMED: NotificationTemplate(
        key=NotificationTemplateKeyEnum.BOOKING_CONFIRMED,
        title="Booking confirmed",
    ),
    NotificationTemplateKeyEnum.BOOKING_CANCELED: NotificationTemplate(
        key=NotificationTemplateKeyEnum.BOOKING_CANCELED,
        title="Booking canceled",
    ),
    NotificationTemplateKeyEnum.LESSON_REMINDER_24H: NotificationTemplate(
        key=NotificationTemplateKeyEnum.LESSON_REMINDER_24H,
        title="Lesson reminder",
    ),
}


def normalize_template_key(
    template_key: str | NotificationTemplateKeyEnum,
) -> NotificationTemplateKeyEnum:
    """Normalize template key and accept legacy aliases."""
    if isinstance(template_key, NotificationTemplateKeyEnum):
        return template_key

    normalized_key = template_key.strip().lower()
    if not normalized_key:
        raise ValueError("Template key cannot be blank")

    if normalized_key in LEGACY_TEMPLATE_KEY_ALIASES:
        return LEGACY_TEMPLATE_KEY_ALIASES[normalized_key]

    try:
        return NotificationTemplateKeyEnum(normalized_key)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Unknown notification template key: {template_key}") from exc


def render_template(
    template_key: str | NotificationTemplateKeyEnum,
    payload: dict[str, Any] | None = None,
) -> RenderedNotificationTemplate:
    """Render title/body from template key and payload context."""
    normalized_key = normalize_template_key(template_key)
    template = TEMPLATE_REGISTRY[normalized_key]
    context = payload or {}
    return RenderedNotificationTemplate(
        template_key=normalized_key,
        title=template.title,
        body=template.render_body(context),
    )
