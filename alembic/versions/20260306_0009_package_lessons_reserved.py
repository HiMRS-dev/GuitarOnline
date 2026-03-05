"""Add lessons_reserved counter to lesson packages

Revision ID: 20260306_0009
Revises: 20260305_0008
Create Date: 2026-03-06 00:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0009"
down_revision: str | None = "20260305_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.add_column(
            sa.Column(
                "lessons_reserved",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.alter_column("lessons_reserved", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.drop_column("lessons_reserved")
