"""Add teacher status enum with backfill from is_approved

Revision ID: 20260304_0002
Revises: 20260219_0001
Create Date: 2026-03-04 23:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260304_0002"
down_revision: str | None = "20260219_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


teacher_status_enum = sa.Enum(
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
            "status",
            teacher_status_enum,
            nullable=True,
            server_default="pending",
        ),
    )
    op.execute(
        """
        UPDATE teacher_profiles
        SET status = CASE
            WHEN is_approved = true THEN 'verified'
            ELSE 'pending'
        END
        """,
    )
    op.alter_column(
        "teacher_profiles",
        "status",
        nullable=False,
        server_default="pending",
    )
    op.create_index(
        "ix_teacher_profiles_status",
        "teacher_profiles",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_teacher_profiles_status", table_name="teacher_profiles")
    op.drop_column("teacher_profiles", "status")
