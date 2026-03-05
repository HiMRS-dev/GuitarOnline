"""Add blocked slot status and block metadata fields

Revision ID: 20260305_0004
Revises: 20260305_0003
Create Date: 2026-03-05 12:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_0004"
down_revision: str | None = "20260305_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


slot_status_enum_old = sa.Enum(
    "open",
    "hold",
    "booked",
    "canceled",
    name="slot_status_enum",
    native_enum=False,
)
slot_status_enum_new = sa.Enum(
    "open",
    "hold",
    "booked",
    "canceled",
    "blocked",
    name="slot_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("availability_slots") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=slot_status_enum_old,
            type_=slot_status_enum_new,
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("block_reason", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("blocked_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_availability_slots_blocked_by_admin_id_users",
            "users",
            ["blocked_by_admin_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_availability_slots_blocked_by_admin_id",
            ["blocked_by_admin_id"],
            unique=False,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE availability_slots SET status = 'canceled' WHERE status = 'blocked'",
    )
    with op.batch_alter_table("availability_slots") as batch_op:
        batch_op.drop_index("ix_availability_slots_blocked_by_admin_id")
        batch_op.drop_constraint(
            "fk_availability_slots_blocked_by_admin_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("blocked_by_admin_id")
        batch_op.drop_column("blocked_at")
        batch_op.drop_column("block_reason")
        batch_op.alter_column(
            "status",
            existing_type=slot_status_enum_new,
            type_=slot_status_enum_old,
            existing_nullable=False,
        )
