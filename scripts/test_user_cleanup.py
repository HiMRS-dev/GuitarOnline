#!/usr/bin/env python3
"""Delete non-synthetic test users while preserving synthetic accounts and one main admin."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.enums import RoleEnum
from app.modules.audit.models import AuditLog
from app.modules.booking.models import Booking
from app.modules.identity.models import Role, User
from app.modules.scheduling.models import AvailabilitySlot

SERVICE_PREFIXES: tuple[str, ...] = (
    "synthetic-ops-",
    "smoke-",
    "perf-probe-",
    "perf-baseline-",
    "demo-",
    "bootstrap-admin",
)
SYNTHETIC_PREFIX = "synthetic-ops-"


@dataclass(frozen=True)
class UserRow:
    user_id: UUID
    email: str
    role: RoleEnum
    created_at: datetime
    is_active: bool
    has_role_change_audit: bool


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _empty_role_counter() -> dict[str, int]:
    return {
        str(RoleEnum.STUDENT): 0,
        str(RoleEnum.TEACHER): 0,
        str(RoleEnum.ADMIN): 0,
    }


def _email_starts_with(email: str, prefix: str) -> bool:
    return email.strip().lower().startswith(prefix)


def _is_service_account(email: str) -> bool:
    normalized = email.strip().lower()
    return any(normalized.startswith(prefix) for prefix in SERVICE_PREFIXES)


def _is_synthetic_account(email: str) -> bool:
    return _email_starts_with(email, SYNTHETIC_PREFIX)


def _classify_origin(row: UserRow) -> str:
    normalized_email = row.email.strip().lower()
    for prefix in SERVICE_PREFIXES:
        if normalized_email.startswith(prefix):
            if prefix == SYNTHETIC_PREFIX:
                return "synthetic_ops"
            return "service_other"

    if row.has_role_change_audit and row.role != RoleEnum.STUDENT:
        return "elevated_via_admin_role_change"
    if row.role == RoleEnum.STUDENT:
        return "likely_self_registration"
    return "legacy_or_unknown_elevated"


async def _load_user_rows(session: AsyncSession) -> list[UserRow]:
    role_change_exists = exists(
        select(AuditLog.id).where(
            AuditLog.action == "admin.user.role.change",
            AuditLog.entity_type == "user",
            AuditLog.entity_id == cast(User.id, String),
        ),
    )
    stmt = (
        select(
            User.id,
            User.email,
            User.created_at,
            User.is_active,
            cast(Role.name, String).label("role_name_raw"),
            role_change_exists.label("has_role_change_audit"),
        )
        .join(Role, Role.id == User.role_id)
        .order_by(User.created_at.asc(), User.id.asc())
    )

    rows: list[UserRow] = []
    for row in (await session.execute(stmt)).all():
        rows.append(
            UserRow(
                user_id=row.id,
                email=str(row.email),
                role=RoleEnum(str(row.role_name_raw).lower()),
                created_at=row.created_at,
                is_active=bool(row.is_active),
                has_role_change_audit=bool(row.has_role_change_audit),
            ),
        )
    return rows


def _build_inventory(rows: list[UserRow]) -> dict[str, Any]:
    by_role_total = _empty_role_counter()
    by_origin_total: Counter[str] = Counter()
    active_total = 0
    inactive_total = 0

    for row in rows:
        role_key = str(row.role)
        by_role_total[role_key] += 1
        if row.is_active:
            active_total += 1
        else:
            inactive_total += 1
        by_origin_total[_classify_origin(row)] += 1

    teachers_total = by_role_total[str(RoleEnum.TEACHER)]
    admins_total = by_role_total[str(RoleEnum.ADMIN)]
    return {
        "users_total": len(rows),
        "users_active": active_total,
        "users_inactive": inactive_total,
        "by_role_total": by_role_total,
        "by_origin_total": dict(sorted(by_origin_total.items())),
        "total_elevated_accounts": teachers_total + admins_total,
        "teachers_total": teachers_total,
        "admins_total": admins_total,
        "provisioned_via_admin_flow": by_origin_total.get("elevated_via_admin_role_change", 0),
        "legacy_or_unknown_source": by_origin_total.get("legacy_or_unknown_elevated", 0),
    }


def _pick_primary_admin(rows: list[UserRow]) -> UserRow:
    candidates = [
        row
        for row in rows
        if row.role == RoleEnum.ADMIN and not _is_service_account(row.email)
    ]
    if not candidates:
        raise RuntimeError("No non-service admin account available to preserve.")
    return min(candidates, key=lambda item: (item.created_at, str(item.user_id)))


def _summarize_deleted_rows(rows: list[UserRow]) -> dict[str, Any]:
    by_role_total = _empty_role_counter()
    for row in rows:
        by_role_total[str(row.role)] += 1
    return {
        "users_total": len(rows),
        "by_role_total": by_role_total,
    }


def _render_markdown(*, generated_at: datetime, payload: dict[str, Any]) -> str:
    pre = payload["pre_cleanup"]
    post = payload["post_cleanup"]
    deleted = payload["deleted"]
    primary_admin = payload["selected_primary_admin"]
    lines = [
        "# Test User Cleanup Report",
        "",
        f"- Generated at (UTC): `{_iso(generated_at)}`",
        f"- Runtime environment: `{payload['app_env']}`",
        f"- Selected primary admin id: `{primary_admin['user_id']}`",
        f"- Selected primary admin created_at_utc: `{primary_admin['created_at_utc']}`",
        "",
        "## Before",
        "",
        f"- Users total: `{pre['users_total']}`",
        (
            "- Roles student/teacher/admin: "
            f"`{pre['by_role_total']['student']}` / "
            f"`{pre['by_role_total']['teacher']}` / "
            f"`{pre['by_role_total']['admin']}`"
        ),
        "",
        "## Deleted",
        "",
        f"- Users deleted: `{deleted['users_total']}`",
        (
            "- Deleted roles student/teacher/admin: "
            f"`{deleted['by_role_total']['student']}` / "
            f"`{deleted['by_role_total']['teacher']}` / "
            f"`{deleted['by_role_total']['admin']}`"
        ),
        f"- Bookings deleted: `{payload['cleanup_actions']['bookings_deleted']}`",
        f"- Slots deleted: `{payload['cleanup_actions']['slots_deleted']}`",
        (
            "- Slots reassigned to preserved admin: "
            f"`{payload['cleanup_actions']['slots_reassigned_to_primary_admin']}`"
        ),
        "",
        "## After",
        "",
        f"- Users total: `{post['users_total']}`",
        (
            "- Roles student/teacher/admin: "
            f"`{post['by_role_total']['student']}` / "
            f"`{post['by_role_total']['teacher']}` / "
            f"`{post['by_role_total']['admin']}`"
        ),
        "",
        "## Origin Snapshot",
        "",
    ]
    for origin_key, count in post["by_origin_total"].items():
        lines.append(f"- `{origin_key}`: `{count}`")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup non-synthetic test users.")
    parser.add_argument(
        "--output-dir",
        default="ops/reports/test-user-cleanup",
        help="Directory where JSON/Markdown reports will be written.",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Optional timestamp suffix override in format YYYYMMDD-HHMMSS.",
    )
    return parser.parse_args()


async def _count_bookings_to_delete(session: AsyncSession, delete_ids: list[UUID]) -> int:
    if not delete_ids:
        return 0
    stmt = select(Booking.id).where(
        or_(
            Booking.student_id.in_(delete_ids),
            Booking.teacher_id.in_(delete_ids),
        ),
    )
    return len((await session.scalars(stmt)).all())


async def _count_slots_to_delete(session: AsyncSession, delete_ids: list[UUID]) -> int:
    if not delete_ids:
        return 0
    stmt = select(AvailabilitySlot.id).where(AvailabilitySlot.teacher_id.in_(delete_ids))
    return len((await session.scalars(stmt)).all())


async def _count_slots_to_reassign(
    session: AsyncSession,
    *,
    delete_ids: list[UUID],
) -> int:
    if not delete_ids:
        return 0
    stmt = select(AvailabilitySlot.id).where(
        AvailabilitySlot.created_by_admin_id.in_(delete_ids),
        AvailabilitySlot.teacher_id.notin_(delete_ids),
    )
    return len((await session.scalars(stmt)).all())


async def async_main(args: argparse.Namespace) -> int:
    settings = get_settings()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC)
    timestamp = args.timestamp or generated_at.strftime("%Y%m%d-%H%M%S")

    async with SessionLocal() as session:
        pre_rows = await _load_user_rows(session)
        primary_admin = _pick_primary_admin(pre_rows)
        keep_ids = {
            row.user_id
            for row in pre_rows
            if _is_synthetic_account(row.email)
        }
        keep_ids.add(primary_admin.user_id)

        deleted_rows = [row for row in pre_rows if row.user_id not in keep_ids]
        delete_ids = [row.user_id for row in deleted_rows]

        bookings_deleted = await _count_bookings_to_delete(session, delete_ids)
        slots_deleted = await _count_slots_to_delete(session, delete_ids)
        slots_reassigned = await _count_slots_to_reassign(session, delete_ids=delete_ids)

        if delete_ids:
            try:
                await session.execute(
                    delete(Booking).where(
                        or_(
                            Booking.student_id.in_(delete_ids),
                            Booking.teacher_id.in_(delete_ids),
                        ),
                    ),
                )
                await session.execute(
                    update(AvailabilitySlot)
                    .where(
                        AvailabilitySlot.created_by_admin_id.in_(delete_ids),
                        AvailabilitySlot.teacher_id.notin_(delete_ids),
                    )
                    .values(created_by_admin_id=primary_admin.user_id),
                )
                await session.execute(
                    delete(AvailabilitySlot).where(
                        AvailabilitySlot.teacher_id.in_(delete_ids),
                    ),
                )
                await session.execute(
                    delete(User).where(User.id.in_(delete_ids)),
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        post_rows = await _load_user_rows(session)

    pre_summary = _build_inventory(pre_rows)
    post_summary = _build_inventory(post_rows)
    deleted_summary = _summarize_deleted_rows(deleted_rows)

    payload = {
        "generated_at_utc": _iso(generated_at),
        "app_env": str(settings.app_env),
        "selected_primary_admin": {
            "user_id": str(primary_admin.user_id),
            "created_at_utc": _iso(primary_admin.created_at),
        },
        "pre_cleanup": pre_summary,
        "deleted": deleted_summary,
        "cleanup_actions": {
            "bookings_deleted": bookings_deleted,
            "slots_deleted": slots_deleted,
            "slots_reassigned_to_primary_admin": slots_reassigned,
        },
        "post_cleanup": post_summary,
        "summary": {
            "users_total": post_summary["users_total"],
            "users_active": post_summary["users_active"],
            "users_inactive": post_summary["users_inactive"],
            "by_role_total": post_summary["by_role_total"],
            "by_origin_total": post_summary["by_origin_total"],
            "total_elevated_accounts": post_summary["total_elevated_accounts"],
            "teachers_total": post_summary["teachers_total"],
            "admins_total": post_summary["admins_total"],
            "provisioned_via_admin_flow": post_summary["provisioned_via_admin_flow"],
            "legacy_or_unknown_source": post_summary["legacy_or_unknown_source"],
        },
    }

    json_path = output_dir / f"test-user-cleanup-{timestamp}.json"
    md_path = output_dir / f"test-user-cleanup-{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(
        _render_markdown(
            generated_at=generated_at,
            payload=payload,
        ),
        encoding="utf-8",
    )

    print(f"test_user_cleanup_json={json_path}")
    print(f"test_user_cleanup_markdown={md_path}")
    print("test_user_cleanup_status=success")
    print(f"elevated_account_audit_json={json_path}")
    print(f"elevated_account_audit_markdown={md_path}")
    print("elevated_account_audit_status=success")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
