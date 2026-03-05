"""Add payment provider identity fields and partial unique index.

Revision ID: 20260306_0011
Revises: 20260306_0010
Create Date: 2026-03-06 02:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0011"
down_revision: str | None = "20260306_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("provider_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("provider_payment_id", sa.String(length=128), nullable=True))

    op.execute(
        """
        UPDATE payments
        SET provider_name = 'manual_paid'
        WHERE provider_name IS NULL
        """,
    )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column(
            "provider_name",
            existing_type=sa.String(length=64),
            nullable=False,
        )

    op.create_index(
        "uq_payments_provider_payment_id_not_null",
        "payments",
        ["provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_payments_provider_payment_id_not_null", table_name="payments")
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("provider_payment_id")
        batch_op.drop_column("provider_name")
