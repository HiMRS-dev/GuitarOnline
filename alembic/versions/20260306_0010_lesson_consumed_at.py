"""Add consumed_at marker for lesson consumption idempotency

Revision ID: 20260306_0010
Revises: 20260306_0009
Create Date: 2026-03-06 00:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0010"
down_revision: str | None = "20260306_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_column("consumed_at")
