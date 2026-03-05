"""Add template_key field to notifications.

Revision ID: 20260306_0015
Revises: 20260306_0014
Create Date: 2026-03-06 05:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0015"
down_revision: str | None = "20260306_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("template_key", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_notifications_template_key", ["template_key"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("ix_notifications_template_key")
        batch_op.drop_column("template_key")
