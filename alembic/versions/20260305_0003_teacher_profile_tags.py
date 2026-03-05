"""Add teacher profile tags table for admin filtering

Revision ID: 20260305_0003
Revises: 20260304_0002
Create Date: 2026-03-05 10:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_0003"
down_revision: str | None = "20260304_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teacher_profile_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("teacher_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["teacher_profile_id"],
            ["teacher_profiles.id"],
            name="fk_teacher_profile_tags_teacher_profile_id_teacher_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_teacher_profile_tags"),
        sa.UniqueConstraint(
            "teacher_profile_id",
            "tag",
            name="uq_teacher_profile_tags_profile_tag",
        ),
    )
    op.create_index(
        "ix_teacher_profile_tags_teacher_profile_id",
        "teacher_profile_tags",
        ["teacher_profile_id"],
        unique=False,
    )
    op.create_index("ix_teacher_profile_tags_tag", "teacher_profile_tags", ["tag"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_teacher_profile_tags_tag", table_name="teacher_profile_tags")
    op.drop_index("ix_teacher_profile_tags_teacher_profile_id", table_name="teacher_profile_tags")
    op.drop_table("teacher_profile_tags")
