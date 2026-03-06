"""Add PostgreSQL trigram indexes for admin teacher search.

Revision ID: 20260306_0018
Revises: 20260306_0017
Create Date: 2026-03-06 09:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0018"
down_revision: str | None = "20260306_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_teacher_profiles_display_name_trgm "
        "ON teacher_profiles USING gin (display_name gin_trgm_ops)",
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_email_trgm "
        "ON users USING gin (email gin_trgm_ops)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_users_email_trgm")
    op.execute("DROP INDEX IF EXISTS ix_teacher_profiles_display_name_trgm")
