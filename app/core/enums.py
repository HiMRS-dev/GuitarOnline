"""Core enums used across modules."""

from enum import StrEnum


class RoleEnum(StrEnum):
    """System roles."""

    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class AppEnvEnum(StrEnum):
    """Runtime environment profile."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class SlotStatusEnum(StrEnum):
    """Availability slot status."""

    OPEN = "open"
    HOLD = "hold"
    BOOKED = "booked"
    CANCELED = "canceled"
    BLOCKED = "blocked"


class SlotBookingAggregateStatusEnum(StrEnum):
    """Aggregated booking state for admin slot views."""

    OPEN = "open"
    HELD = "held"
    CONFIRMED = "confirmed"


class BookingStatusEnum(StrEnum):
    """Booking lifecycle status."""

    HOLD = "hold"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"
    EXPIRED = "expired"


class TeacherStatusEnum(StrEnum):
    """Teacher profile lifecycle status."""

    ACTIVE = "active"
    DISABLED = "disabled"


class PackageStatusEnum(StrEnum):
    """Lesson package status."""

    ACTIVE = "active"
    EXPIRED = "expired"
    DEPLETED = "depleted"
    CANCELED = "canceled"


class PaymentStatusEnum(StrEnum):
    """Payment processing status."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class LessonStatusEnum(StrEnum):
    """Lesson status."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELED = "canceled"
    NO_SHOW = "no_show"


class NotificationStatusEnum(StrEnum):
    """Notification delivery status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationTemplateKeyEnum(StrEnum):
    """Supported notification template keys."""

    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_CANCELED = "booking_canceled"
    LESSON_REMINDER_24H = "lesson_reminder_24h"


class OutboxStatusEnum(StrEnum):
    """Outbox event status for integration publishing."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
