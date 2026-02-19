"""Initial schema

Revision ID: 20260219_0001
Revises:
Create Date: 2026-02-19 22:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260219_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


role_enum = sa.Enum("student", "teacher", "admin", name="role_enum", native_enum=False)
slot_status_enum = sa.Enum("open", "hold", "booked", "canceled", name="slot_status_enum", native_enum=False)
booking_status_enum = sa.Enum("hold", "confirmed", "canceled", "expired", name="booking_status_enum", native_enum=False)
package_status_enum = sa.Enum("active", "expired", "canceled", name="package_status_enum", native_enum=False)
payment_status_enum = sa.Enum("pending", "succeeded", "failed", "refunded", name="payment_status_enum", native_enum=False)
lesson_status_enum = sa.Enum("scheduled", "completed", "canceled", name="lesson_status_enum", native_enum=False)
notification_status_enum = sa.Enum("pending", "sent", "failed", name="notification_status_enum", native_enum=False)
outbox_status_enum = sa.Enum("pending", "processed", "failed", name="outbox_status_enum", native_enum=False)


def _id_col() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False)


def _created_col() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _updated_col() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "roles",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("name", role_enum, nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "users",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_users_role_id_roles", ondelete="RESTRICT"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "refresh_tokens",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("token_id", name="uq_refresh_tokens_token_id"),
    )
    op.create_index("ix_refresh_tokens_token_id", "refresh_tokens", ["token_id"], unique=False)

    op.create_table(
        "teacher_profiles",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("experience_years", sa.Integer(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_teacher_profiles_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_teacher_profiles_user_id"),
    )

    op.create_table(
        "availability_slots",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", slot_status_enum, nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], name="fk_availability_slots_teacher_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["users.id"],
            name="fk_availability_slots_created_by_admin_id_users",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_availability_slots_teacher_id", "availability_slots", ["teacher_id"], unique=False)
    op.create_index("ix_availability_slots_created_by_admin_id", "availability_slots", ["created_by_admin_id"], unique=False)
    op.create_index("ix_availability_slots_start_at", "availability_slots", ["start_at"], unique=False)
    op.create_index("ix_availability_slots_status", "availability_slots", ["status"], unique=False)

    op.create_table(
        "lesson_packages",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lessons_total", sa.Integer(), nullable=False),
        sa.Column("lessons_left", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", package_status_enum, nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_lesson_packages_student_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_lesson_packages_student_id", "lesson_packages", ["student_id"], unique=False)

    op.create_table(
        "bookings",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", booking_status_enum, nullable=False),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=512), nullable=True),
        sa.Column("refund_returned", sa.Boolean(), nullable=False),
        sa.Column("rescheduled_from_booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["slot_id"], ["availability_slots.id"], name="fk_bookings_slot_id_availability_slots", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_bookings_student_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], name="fk_bookings_teacher_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["lesson_packages.id"], name="fk_bookings_package_id_lesson_packages", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rescheduled_from_booking_id"], ["bookings.id"], name="fk_bookings_rescheduled_from_booking_id_bookings", ondelete="SET NULL"),
        sa.UniqueConstraint("slot_id", name="uq_bookings_slot_id"),
    )
    op.create_index("ix_bookings_student_id", "bookings", ["student_id"], unique=False)
    op.create_index("ix_bookings_teacher_id", "bookings", ["teacher_id"], unique=False)
    op.create_index("ix_bookings_status", "bookings", ["status"], unique=False)

    op.create_table(
        "lessons",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", lesson_status_enum, nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], name="fk_lessons_booking_id_bookings", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], name="fk_lessons_student_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], name="fk_lessons_teacher_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("booking_id", name="uq_lessons_booking_id"),
    )
    op.create_index("ix_lessons_booking_id", "lessons", ["booking_id"], unique=False)
    op.create_index("ix_lessons_student_id", "lessons", ["student_id"], unique=False)
    op.create_index("ix_lessons_teacher_id", "lessons", ["teacher_id"], unique=False)
    op.create_index("ix_lessons_status", "lessons", ["status"], unique=False)

    op.create_table(
        "payments",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", payment_status_enum, nullable=False),
        sa.Column("external_reference", sa.String(length=128), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["package_id"], ["lesson_packages.id"], name="fk_payments_package_id_lesson_packages", ondelete="CASCADE"),
    )

    op.create_table(
        "notifications",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", notification_status_enum, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_status", "notifications", ["status"], unique=False)

    op.create_table(
        "admin_actions",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], name="fk_admin_actions_admin_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_admin_actions_admin_id", "admin_actions", ["admin_id"], unique=False)

    op.create_table(
        "audit_logs",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_audit_logs_actor_id_users", ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)

    op.create_table(
        "outbox_events",
        _id_col(),
        _created_col(),
        _updated_col(),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", outbox_status_enum, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_outbox_events_aggregate_type", "outbox_events", ["aggregate_type"], unique=False)
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"], unique=False)
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"], unique=False)
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_type", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_type", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_admin_actions_admin_id", table_name="admin_actions")
    op.drop_table("admin_actions")

    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_table("payments")

    op.drop_index("ix_lessons_status", table_name="lessons")
    op.drop_index("ix_lessons_teacher_id", table_name="lessons")
    op.drop_index("ix_lessons_student_id", table_name="lessons")
    op.drop_index("ix_lessons_booking_id", table_name="lessons")
    op.drop_table("lessons")

    op.drop_index("ix_bookings_status", table_name="bookings")
    op.drop_index("ix_bookings_teacher_id", table_name="bookings")
    op.drop_index("ix_bookings_student_id", table_name="bookings")
    op.drop_table("bookings")

    op.drop_index("ix_lesson_packages_student_id", table_name="lesson_packages")
    op.drop_table("lesson_packages")

    op.drop_index("ix_availability_slots_status", table_name="availability_slots")
    op.drop_index("ix_availability_slots_start_at", table_name="availability_slots")
    op.drop_index("ix_availability_slots_created_by_admin_id", table_name="availability_slots")
    op.drop_index("ix_availability_slots_teacher_id", table_name="availability_slots")
    op.drop_table("availability_slots")

    op.drop_table("teacher_profiles")

    op.drop_index("ix_refresh_tokens_token_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_table("roles")
