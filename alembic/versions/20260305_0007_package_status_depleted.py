"""Add DEPLETED to package status enum

Revision ID: 20260305_0007
Revises: 20260305_0006
Create Date: 2026-03-05 23:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_0007"
down_revision: str | None = "20260305_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


package_status_enum_old = sa.Enum(
    "active",
    "expired",
    "canceled",
    name="package_status_enum",
    native_enum=False,
)
package_status_enum_new = sa.Enum(
    "active",
    "expired",
    "depleted",
    "canceled",
    name="package_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=package_status_enum_old,
            type_=package_status_enum_new,
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE lesson_packages SET status = 'canceled' WHERE status = 'depleted'",
    )
    with op.batch_alter_table("lesson_packages") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=package_status_enum_new,
            type_=package_status_enum_old,
            existing_nullable=False,
        )
