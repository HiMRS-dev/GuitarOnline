"""Fix lesson package reserved/balance check constraint semantics.

Revision ID: 20260309_0020
Revises: 20260309_0019
Create Date: 2026-03-09 13:35:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260309_0020"
down_revision: str | None = "20260309_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_balance_lte_total",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_reserved_lte_left",
            "lessons_reserved <= lessons_left",
        )


def downgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.drop_constraint(
            "ck_lesson_packages_lessons_reserved_lte_left",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_lesson_packages_lessons_balance_lte_total",
            "lessons_left + lessons_reserved <= lessons_total",
        )
