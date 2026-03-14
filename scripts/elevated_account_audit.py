#!/usr/bin/env python3
"""Generate elevated-account audit report for teacher/admin users."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.enums import RoleEnum, TeacherStatusEnum
from app.modules.audit.models import AuditLog
from app.modules.identity.models import Role, User
from app.modules.teachers.models import TeacherProfile


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _teacher_status_key(status: TeacherStatusEnum | None) -> str:
    if status is None:
        return "missing_profile"
    if status == TeacherStatusEnum.DISABLED:
        return str(status).lower()
    return str(TeacherStatusEnum.ACTIVE)


@dataclass(frozen=True)
class ElevatedAccountEntry:
    user_id: UUID
    email: str
    role: RoleEnum
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    teacher_profile_id: UUID | None
    teacher_status: TeacherStatusEnum | None
    access_source: str
    access_assigned_at: datetime | None
    access_assigned_by_admin_id: UUID | None

    def as_json(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "email": self.email,
            "role": str(self.role),
            "timezone": self.timezone,
            "is_active": self.is_active,
            "created_at_utc": _iso(self.created_at),
            "updated_at_utc": _iso(self.updated_at),
            "teacher_profile_id": str(self.teacher_profile_id) if self.teacher_profile_id else None,
            "teacher_status": (
                str(self.teacher_status) if self.teacher_status is not None else "missing_profile"
            ),
            "access_source": self.access_source,
            "access_assigned_at_utc": _iso(self.access_assigned_at),
            "access_assigned_by_admin_id": (
                str(self.access_assigned_by_admin_id)
                if self.access_assigned_by_admin_id
                else None
            ),
        }


def build_summary(entries: list[ElevatedAccountEntry]) -> dict[str, int]:
    summary = {
        "total_elevated_accounts": len(entries),
        "teachers_total": 0,
        "admins_total": 0,
        "active_accounts": 0,
        "inactive_accounts": 0,
        "assigned_via_admin_role_change": 0,
        "legacy_or_unknown_source": 0,
        "teacher_status_active": 0,
        "teacher_status_disabled": 0,
        "teacher_status_missing_profile": 0,
    }
    for entry in entries:
        if entry.is_active:
            summary["active_accounts"] += 1
        else:
            summary["inactive_accounts"] += 1

        if entry.access_source == "admin.user.role.change":
            summary["assigned_via_admin_role_change"] += 1
        else:
            summary["legacy_or_unknown_source"] += 1

        if entry.role == RoleEnum.TEACHER:
            summary["teachers_total"] += 1
            status_key = _teacher_status_key(entry.teacher_status)
            summary[f"teacher_status_{status_key}"] += 1
        elif entry.role == RoleEnum.ADMIN:
            summary["admins_total"] += 1
    return summary


def render_markdown(
    *,
    generated_at_utc: datetime,
    app_env: str,
    summary: dict[str, int],
    rows: list[dict[str, Any]],
) -> str:
    lines: list[str] = [
        "# Elevated Account Audit Report",
        "",
        f"- Generated at (UTC): `{_iso(generated_at_utc)}`",
        f"- Runtime environment: `{app_env}`",
        "",
        "## Summary",
        "",
        f"- Total elevated accounts: `{summary['total_elevated_accounts']}`",
        f"- Teachers: `{summary['teachers_total']}`",
        f"- Admins: `{summary['admins_total']}`",
        f"- Active: `{summary['active_accounts']}`",
        f"- Inactive: `{summary['inactive_accounts']}`",
        (
            "- Assigned via `admin.user.role.change`: "
            f"`{summary['assigned_via_admin_role_change']}`"
        ),
        f"- Legacy/unknown source: `{summary['legacy_or_unknown_source']}`",
        "",
        "## Teacher Status",
        "",
        f"- Active: `{summary['teacher_status_active']}`",
        f"- Disabled: `{summary['teacher_status_disabled']}`",
        f"- Missing profile: `{summary['teacher_status_missing_profile']}`",
        "",
        "## Entries",
        "",
        "| email | role | active | teacher_status | access_source | access_assigned_at_utc |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row['email']} | "
            f"{row['role']} | "
            f"{row['is_active']} | "
            f"{row['teacher_status']} | "
            f"{row['access_source']} | "
            f"{row['access_assigned_at_utc'] or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


async def load_entries(session: AsyncSession) -> list[ElevatedAccountEntry]:
    role_change_at_subquery = (
        select(AuditLog.created_at)
        .where(
            AuditLog.action == "admin.user.role.change",
            AuditLog.entity_type == "user",
            AuditLog.entity_id == cast(User.id, String),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    role_change_by_subquery = (
        select(AuditLog.actor_id)
        .where(
            AuditLog.action == "admin.user.role.change",
            AuditLog.entity_type == "user",
            AuditLog.entity_id == cast(User.id, String),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(
            User.id,
            User.email,
            User.timezone,
            User.is_active,
            User.created_at,
            User.updated_at,
            cast(Role.name, String).label("role_name_raw"),
            TeacherProfile.id.label("teacher_profile_id"),
            cast(TeacherProfile.status, String).label("teacher_status_raw"),
            role_change_at_subquery.label("role_change_at"),
            role_change_by_subquery.label("role_change_by_admin_id"),
        )
        .join(Role, Role.id == User.role_id)
        .outerjoin(TeacherProfile, TeacherProfile.user_id == User.id)
        .where(func.lower(cast(Role.name, String)).in_(("teacher", "admin")))
        .order_by(User.created_at.asc(), User.id.asc())
    )

    entries: list[ElevatedAccountEntry] = []
    for row in (await session.execute(stmt)).all():
        role_raw = str(row.role_name_raw).lower()
        try:
            role = RoleEnum(role_raw)
        except ValueError:
            continue

        teacher_status: TeacherStatusEnum | None = None
        if row.teacher_profile_id is not None and row.teacher_status_raw is not None:
            try:
                teacher_status = TeacherStatusEnum(str(row.teacher_status_raw).lower())
            except ValueError:
                teacher_status = None
            else:
                if teacher_status != TeacherStatusEnum.DISABLED:
                    teacher_status = TeacherStatusEnum.ACTIVE

        access_source = "admin.user.role.change"
        access_assigned_at = row.role_change_at
        access_assigned_by_admin_id = row.role_change_by_admin_id
        if access_assigned_at is None:
            access_source = "legacy_or_unknown"

        entries.append(
            ElevatedAccountEntry(
                user_id=row.id,
                email=row.email,
                role=role,
                timezone=row.timezone,
                is_active=row.is_active,
                created_at=row.created_at,
                updated_at=row.updated_at,
                teacher_profile_id=row.teacher_profile_id,
                teacher_status=teacher_status,
                access_source=access_source,
                access_assigned_at=access_assigned_at,
                access_assigned_by_admin_id=access_assigned_by_admin_id,
            ),
        )
    return entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate elevated account audit report.")
    parser.add_argument(
        "--output-dir",
        default="ops/reports/elevated-account-audit",
        help="Directory where JSON/Markdown reports will be written.",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Optional timestamp suffix override in format YYYYMMDD-HHMMSS.",
    )
    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC)
    timestamp = args.timestamp or generated_at.strftime("%Y%m%d-%H%M%S")

    async with SessionLocal() as session:
        entries = await load_entries(session)

    rows = [entry.as_json() for entry in entries]
    summary = build_summary(entries)
    payload = {
        "generated_at_utc": _iso(generated_at),
        "app_env": str(settings.app_env),
        "summary": summary,
        "entries": rows,
    }

    json_path = output_dir / f"elevated-account-audit-{timestamp}.json"
    md_path = output_dir / f"elevated-account-audit-{timestamp}.md"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(
        render_markdown(
            generated_at_utc=generated_at,
            app_env=str(settings.app_env),
            summary=summary,
            rows=rows,
        ),
        encoding="utf-8",
    )

    print(f"elevated_account_audit_json={json_path}")
    print(f"elevated_account_audit_markdown={md_path}")
    print("elevated_account_audit_status=success")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
