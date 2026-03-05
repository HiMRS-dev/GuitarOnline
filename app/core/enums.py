"""Core enums used across modules."""

from enum import StrEnum


class RoleEnum(StrEnum):
    """System roles."""

    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


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
    """Teacher profile moderation status."""

    PENDING = "pending"
    VERIFIED = "verified"
    DISABLED = "disabled"


class PackageStatusEnum(StrEnum):
    """Lesson package status."""

    ACTIVE = "active"
    EXPIRED = "expired"
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


class OutboxStatusEnum(StrEnum):
    """Outbox event status for integration publishing."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
