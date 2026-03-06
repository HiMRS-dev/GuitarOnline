"""Add indexes for admin performance-heavy queries.

Revision ID: 20260306_0017
Revises: 20260306_0016
Create Date: 2026-03-06 09:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0017"
down_revision: str | None = "20260306_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("availability_slots") as batch_op:
        batch_op.create_index(
            "ix_availability_slots_teacher_start_at",
            ["teacher_id", "start_at"],
            unique=False,
        )

    with op.batch_alter_table("bookings") as batch_op:
        batch_op.create_index(
            "ix_bookings_slot_status",
            ["slot_id", "status"],
            unique=False,
        )

    with op.batch_alter_table("teacher_profiles") as batch_op:
        batch_op.create_index(
            "ix_teacher_profiles_created_at",
            ["created_at"],
            unique=False,
        )

    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.create_index(
            "ix_lesson_packages_created_at",
            ["created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_lesson_packages_status_created_at",
            ["status", "created_at"],
            unique=False,
        )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.create_index(
            "ix_payments_status_created_at",
            ["status", "created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_payments_package_status_created_at",
            ["package_id", "status", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_index("ix_payments_package_status_created_at")
        batch_op.drop_index("ix_payments_status_created_at")

    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.drop_index("ix_lesson_packages_status_created_at")
        batch_op.drop_index("ix_lesson_packages_created_at")

    with op.batch_alter_table("teacher_profiles") as batch_op:
        batch_op.drop_index("ix_teacher_profiles_created_at")

    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_index("ix_bookings_slot_status")

    with op.batch_alter_table("availability_slots") as batch_op:
        batch_op.drop_index("ix_availability_slots_teacher_start_at")
