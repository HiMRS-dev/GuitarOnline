"""Add persistent teacher weekly schedule windows.

Revision ID: 20260329_0023
Revises: 20260327_0022
Create Date: 2026-03-29 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260329_0023"
down_revision: str | None = "20260327_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teacher_weekly_schedule_windows",
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_local_time", sa.Time(), nullable=False),
        sa.Column("end_local_time", sa.Time(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name=op.f("ck_teacher_weekly_schedule_windows_teacher_weekly_schedule_windows_weekday_range"),
        ),
        sa.CheckConstraint(
            "end_local_time > start_local_time",
            name=op.f("ck_teacher_weekly_schedule_windows_teacher_weekly_schedule_windows_time_range"),
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["users.id"],
            name=op.f("fk_teacher_weekly_schedule_windows_teacher_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teacher_weekly_schedule_windows")),
    )
    op.create_index(
        op.f("ix_teacher_weekly_schedule_windows_teacher_id"),
        "teacher_weekly_schedule_windows",
        ["teacher_id"],
        unique=False,
    )
    op.create_index(
        "ix_teacher_weekly_schedule_windows_teacher_weekday",
        "teacher_weekly_schedule_windows",
        ["teacher_id", "weekday"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_teacher_weekly_schedule_windows_teacher_weekday",
        table_name="teacher_weekly_schedule_windows",
    )
    op.drop_index(
        op.f("ix_teacher_weekly_schedule_windows_teacher_id"),
        table_name="teacher_weekly_schedule_windows",
    )
    op.drop_table("teacher_weekly_schedule_windows")
