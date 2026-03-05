"""Add idempotency_key field to notifications.

Revision ID: 20260306_0016
Revises: 20260306_0015
Create Date: 2026-03-06 07:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0016"
down_revision: str | None = "20260306_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=191), nullable=True))
        batch_op.create_index(
            "uq_notifications_idempotency_key",
            ["idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("uq_notifications_idempotency_key")
        batch_op.drop_column("idempotency_key")
