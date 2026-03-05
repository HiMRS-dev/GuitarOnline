"""Use active-state unique index for bookings.slot_id

Revision ID: 20260305_0006
Revises: 20260305_0005
Create Date: 2026-03-05 23:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_0006"
down_revision: str | None = "20260305_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_BOOKING_WHERE = "status IN ('hold', 'confirmed')"


def upgrade() -> None:
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_constraint("uq_bookings_slot_id", type_="unique")
    op.create_index(
        "uq_bookings_slot_id_active",
        "bookings",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_BOOKING_WHERE),
    )


def downgrade() -> None:
    op.drop_index("uq_bookings_slot_id_active", table_name="bookings")
    op.execute(
        """
        DELETE FROM bookings
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY slot_id
                    ORDER BY created_at DESC, id DESC
                ) AS row_num
                FROM bookings
            ) ranked
            WHERE ranked.row_num > 1
        )
        """,
    )
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.create_unique_constraint("uq_bookings_slot_id", ["slot_id"])
