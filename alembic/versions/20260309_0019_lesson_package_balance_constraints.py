"""Add defensive lesson package balance constraints.

Revision ID: 20260309_0019
Revises: 20260306_0018
Create Date: 2026-03-09 12:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260309_0019"
down_revision: str | None = "20260306_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_total_positive",
            "lessons_total > 0",
        )
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_left_non_negative",
            "lessons_left >= 0",
        )
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_reserved_non_negative",
            "lessons_reserved >= 0",
        )
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_left_lte_total",
            "lessons_left <= lessons_total",
        )
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_reserved_lte_total",
            "lessons_reserved <= lessons_total",
        )
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_balance_lte_total",
            "lessons_left + lessons_reserved <= lessons_total",
        )


def downgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_balance_lte_total",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_reserved_lte_total",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_left_lte_total",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_reserved_non_negative",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_left_non_negative",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_total_positive",
            type_="check",
        )
