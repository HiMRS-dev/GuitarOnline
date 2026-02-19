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


class BookingStatusEnum(StrEnum):
    """Booking lifecycle status."""

    HOLD = "hold"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"
    EXPIRED = "expired"


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
