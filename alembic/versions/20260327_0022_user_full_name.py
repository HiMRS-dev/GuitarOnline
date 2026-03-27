"""Add full_name to users and backfill existing accounts.

Revision ID: 20260327_0022
Revises: 20260314_0021
Create Date: 2026-03-27 12:30:00
"""

from __future__ import annotations

from collections.abc import Sequence
import re

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260327_0022"
down_revision: str | None = "20260314_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


users_table = sa.table(
    "users",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("email", sa.String(length=255)),
    sa.column("full_name", sa.String(length=255)),
)

_FULL_NAME_BY_EMAIL: dict[str, str] = {
    "bootstrap-admin@guitaronline.dev": "Волков Алексей Николаевич",
    "demo-admin@guitaronline.dev": "Иванов Алексей Петрович",
    "demo-teacher-1@guitaronline.dev": "Петров Сергей Андреевич",
    "demo-teacher-2@guitaronline.dev": "Смирнов Павел Игоревич",
    "demo-teacher-3@guitaronline.dev": "Кузнецов Дмитрий Олегович",
    "demo-student-1@guitaronline.dev": "Новиков Илья Сергеевич",
    "demo-student-2@guitaronline.dev": "Васильев Артём Николаевич",
    "demo-student-3@guitaronline.dev": "Фёдоров Максим Андреевич",
    "demo-student-4@guitaronline.dev": "Попов Егор Павлович",
    "demo-student-5@guitaronline.dev": "Лебедев Кирилл Олегович",
    "smoke-admin-1@guitaronline.dev": "Морозов Артём Ильич",
    "smoke-teacher-1@guitaronline.dev": "Никитин Егор Павлович",
    "smoke-student-1@guitaronline.dev": "Фролов Кирилл Денисович",
    "smoke-student-2@guitaronline.dev": "Белов Матвей Сергеевич",
    "synthetic-ops-admin@guitaronline.dev": "Орлов Максим Игоревич",
    "synthetic-ops-teacher@guitaronline.dev": "Ковалёв Павел Андреевич",
    "synthetic-ops-student@guitaronline.dev": "Соколов Илья Дмитриевич",
}

_FULL_NAME_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("deploy-smoke-admin-", "Демидов Артём Сергеевич"),
)


def _build_full_name(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized:
        return "Иванов Алексей Петрович"

    exact_match = _FULL_NAME_BY_EMAIL.get(normalized)
    if exact_match is not None:
        return exact_match

    for prefix, full_name in _FULL_NAME_BY_PREFIX:
        if normalized.startswith(prefix):
            return full_name

    local_part = normalized.split("@", 1)[0]
    if "teacher" in local_part:
        return "Ковалёв Павел Андреевич"
    if "student" in local_part:
        return "Соколов Илья Дмитриевич"
    if "admin" in local_part:
        return "Волков Алексей Николаевич"

    tokens = [token for token in re.split(r"[^a-z0-9]+", local_part) if token]
    if tokens:
        capitalized = " ".join(token.capitalize() for token in tokens[:3])
        return f"Иванов {capitalized} Петрович"[:255]

    return "Иванов Алексей Петрович"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=255), nullable=True),
    )

    connection = op.get_bind()
    rows = connection.execute(sa.select(users_table.c.id, users_table.c.email)).all()
    for row in rows:
        connection.execute(
            users_table.update()
            .where(users_table.c.id == row.id)
            .values(full_name=_build_full_name(row.email)),
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "full_name",
            existing_type=sa.String(length=255),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("full_name")
