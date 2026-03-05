"""Add lesson report fields homework and links.

Revision ID: 20260306_0012
Revises: 20260306_0011
Create Date: 2026-03-06 04:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0012"
down_revision: str | None = "20260306_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("homework", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("links", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_column("links")
        batch_op.drop_column("homework")
