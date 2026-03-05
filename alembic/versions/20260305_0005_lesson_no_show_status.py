"""Add NO_SHOW to lesson status enum

Revision ID: 20260305_0005
Revises: 20260305_0004
Create Date: 2026-03-05 17:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_0005"
down_revision: str | None = "20260305_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


lesson_status_enum_old = sa.Enum(
    "scheduled",
    "completed",
    "canceled",
    name="lesson_status_enum",
    native_enum=False,
)
lesson_status_enum_new = sa.Enum(
    "scheduled",
    "completed",
    "canceled",
    "no_show",
    name="lesson_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=lesson_status_enum_old,
            type_=lesson_status_enum_new,
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute("UPDATE lessons SET status = 'canceled' WHERE status = 'no_show'")
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=lesson_status_enum_new,
            type_=lesson_status_enum_old,
            existing_nullable=False,
        )
