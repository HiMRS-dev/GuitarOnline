"""Remove teacher verify artifacts from schema.

Revision ID: 20260314_0021
Revises: 20260309_0020
Create Date: 2026-03-14 20:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260314_0021"
down_revision: str | None = "20260309_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


teacher_status_active_enum = sa.Enum(
    "active",
    "disabled",
    name="teacher_status_enum",
    native_enum=False,
)

teacher_status_legacy_enum = sa.Enum(
    "pending",
    "verified",
    "disabled",
    name="teacher_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "teacher_profiles",
        sa.Column(
            "status_v2",
            teacher_status_active_enum,
            nullable=True,
            server_default="active",
        ),
    )
    op.execute(
        """
        UPDATE teacher_profiles
        SET status_v2 = CASE
            WHEN status = 'disabled' THEN 'disabled'
            ELSE 'active'
        END
        """,
    )

    with op.batch_alter_table("teacher_profiles") as batch_op:
        batch_op.drop_index("ix_teacher_profiles_status")
        batch_op.drop_column("status")
        batch_op.drop_column("is_approved")
        batch_op.alter_column(
            "status_v2",
            existing_type=teacher_status_active_enum,
            new_column_name="status",
            nullable=False,
            server_default="active",
        )
        batch_op.create_index(
            "ix_teacher_profiles_status",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    op.add_column(
        "teacher_profiles",
        sa.Column(
            "status_legacy",
            teacher_status_legacy_enum,
            nullable=True,
            server_default="pending",
        ),
    )
    op.add_column(
        "teacher_profiles",
        sa.Column(
            "is_approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        """
        UPDATE teacher_profiles
        SET status_legacy = CASE
            WHEN status = 'disabled' THEN 'disabled'
            ELSE 'verified'
        END,
        is_approved = CASE
            WHEN status = 'active' THEN true
            ELSE false
        END
        """,
    )

    with op.batch_alter_table("teacher_profiles") as batch_op:
        batch_op.drop_index("ix_teacher_profiles_status")
        batch_op.drop_column("status")
        batch_op.alter_column(
            "status_legacy",
            existing_type=teacher_status_legacy_enum,
            new_column_name="status",
            nullable=False,
            server_default="pending",
        )
        batch_op.alter_column(
            "is_approved",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=None,
        )
        batch_op.create_index(
            "ix_teacher_profiles_status",
            ["status"],
            unique=False,
        )
