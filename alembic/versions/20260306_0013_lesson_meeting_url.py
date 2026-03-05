"""Add meeting_url field to lessons.

Revision ID: 20260306_0013
Revises: 20260306_0012
Create Date: 2026-03-06 04:35:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0013"
down_revision: str | None = "20260306_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("meeting_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_column("meeting_url")
