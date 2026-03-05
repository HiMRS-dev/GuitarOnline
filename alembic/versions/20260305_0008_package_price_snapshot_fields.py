"""Add package price snapshot fields

Revision ID: 20260305_0008
Revises: 20260305_0007
Create Date: 2026-03-05 23:59:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_0008"
down_revision: str | None = "20260305_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.add_column(sa.Column("price_amount", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("price_currency", sa.String(length=3), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.drop_column("price_currency")
        batch_op.drop_column("price_amount")
