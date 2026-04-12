"""Add optional age field to users profile.

Revision ID: 20260412_0024
Revises: 20260329_0023
Create Date: 2026-04-12 22:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260412_0024"
down_revision: str | None = "20260329_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("age", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_users_age_range",
            "age >= 1 AND age <= 120",
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_age_range", type_="check")
        batch_op.drop_column("age")
