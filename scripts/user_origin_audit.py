#!/usr/bin/env python3
"""Generate a read-only user origin summary without exposing user emails."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import String, cast, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.enums import RoleEnum
from app.modules.audit.models import AuditLog
from app.modules.identity.models import Role, User

SERVICE_ACCOUNT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("synthetic_ops", "synthetic-ops-"),
    ("smoke_pool", "smoke-"),
    ("perf_probe", "perf-probe-"),
    ("perf_baseline", "perf-baseline-"),
    ("demo_seed", "demo-"),
    ("bootstrap_admin", "bootstrap-admin"),
)


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


def _classify_origin(*, email: str, role: RoleEnum, has_role_change_audit: bool) -> str:
    normalized_email = email.strip().lower()
    for origin_key, prefix in SERVICE_ACCOUNT_PREFIXES:
        if normalized_email.startswith(prefix):
            return origin_key

    if has_role_change_audit:
        if role == RoleEnum.STUDENT:
            return "student_with_admin_role_history"
        return "elevated_via_admin_role_change"

    if role == RoleEnum.STUDENT:
        return "likely_self_registration"

    if role in {RoleEnum.TEACHER, RoleEnum.ADMIN}:
        return "legacy_or_unknown_elevated"

    return "legacy_or_unknown"


async def _load_user_rows(session: AsyncSession) -> list[dict[str, Any]]:
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
            User.created_at,
            User.is_active,
            User.email,
            cast(Role.name, String).label("role_name_raw"),
            role_change_exists.label("has_role_change_audit"),
        )
        .join(Role, Role.id == User.role_id)
        .order_by(User.created_at.asc(), User.id.asc())
    )

    rows: list[dict[str, Any]] = []
    for row in (await session.execute(stmt)).all():
        role_raw = str(row.role_name_raw).lower()
        role = RoleEnum(role_raw)
        rows.append(
            {
                "user_id": str(row.id),
                "created_at_utc": _iso(row.created_at),
                "is_active": bool(row.is_active),
                "role": role,
                "email": str(row.email),
                "has_role_change_audit": bool(row.has_role_change_audit),
            },
        )
    return rows


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "users_total": len(rows),
        "users_active": 0,
        "users_inactive": 0,
        "service_accounts_total": 0,
        "non_service_accounts_total": 0,
        "by_role_total": _empty_role_counter(),
        "by_role_active": _empty_role_counter(),
        "by_role_inactive": _empty_role_counter(),
        "by_origin_total": {},
        "by_origin_and_role": {},
        "origin_methodology": {
            "synthetic_ops": "email prefix synthetic-ops-",
            "smoke_pool": "email prefix smoke-",
            "perf_probe": "email prefix perf-probe-",
            "perf_baseline": "email prefix perf-baseline-",
            "demo_seed": "email prefix demo-",
            "bootstrap_admin": "email prefix bootstrap-admin",
            "elevated_via_admin_role_change": (
                "current non-student role with admin.user.role.change audit"
            ),
            "student_with_admin_role_history": (
                "current student role with admin.user.role.change audit history"
            ),
            "likely_self_registration": (
                "current student role without service prefix and without role-change audit"
            ),
            "legacy_or_unknown_elevated": (
                "current teacher/admin role without service prefix and without role-change audit"
            ),
            "legacy_or_unknown": "fallback for anything else",
        },
    }

    by_origin_counter: Counter[str] = Counter()
    by_origin_and_role: dict[str, dict[str, int]] = {}

    for row in rows:
        role = row["role"]
        role_key = str(role)
        is_active = bool(row["is_active"])
        origin = _classify_origin(
            email=str(row["email"]),
            role=role,
            has_role_change_audit=bool(row["has_role_change_audit"]),
        )

        summary["by_role_total"][role_key] += 1
        if is_active:
            summary["users_active"] += 1
            summary["by_role_active"][role_key] += 1
        else:
            summary["users_inactive"] += 1
            summary["by_role_inactive"][role_key] += 1

        if origin in {
            "synthetic_ops",
            "smoke_pool",
            "perf_probe",
            "perf_baseline",
            "demo_seed",
            "bootstrap_admin",
        }:
            summary["service_accounts_total"] += 1
        else:
            summary["non_service_accounts_total"] += 1

        by_origin_counter[origin] += 1
        by_origin_and_role.setdefault(
            origin,
            {
                str(RoleEnum.STUDENT): 0,
                str(RoleEnum.TEACHER): 0,
                str(RoleEnum.ADMIN): 0,
            },
        )
        by_origin_and_role[origin][role_key] += 1

    summary["by_origin_total"] = dict(sorted(by_origin_counter.items()))
    summary["by_origin_and_role"] = {
        key: by_origin_and_role[key]
        for key in sorted(by_origin_and_role)
    }
    return summary


def _render_markdown(*, generated_at_utc: datetime, app_env: str, summary: dict[str, Any]) -> str:
    lines = [
        "# User Origin Audit Report",
        "",
        f"- Generated at (UTC): `{_iso(generated_at_utc)}`",
        f"- Runtime environment: `{app_env}`",
        "",
        "## Totals",
        "",
        f"- Users total: `{summary['users_total']}`",
        f"- Active / inactive: `{summary['users_active']}` / `{summary['users_inactive']}`",
        (
            "- Service/test accounts / non-service accounts: "
            f"`{summary['service_accounts_total']}` / `{summary['non_service_accounts_total']}`"
        ),
        "",
        "## By Role",
        "",
        "| Role | Total | Active | Inactive |",
        "| --- | ---: | ---: | ---: |",
    ]

    for role_key in (str(RoleEnum.STUDENT), str(RoleEnum.TEACHER), str(RoleEnum.ADMIN)):
        lines.append(
            "| "
            f"`{role_key}` | "
            f"{summary['by_role_total'][role_key]} | "
            f"{summary['by_role_active'][role_key]} | "
            f"{summary['by_role_inactive'][role_key]} |"
        )

    lines.extend(
        [
            "",
            "## By Origin",
            "",
            "| Origin | Total | student | teacher | admin |",
            "| --- | ---: | ---: | ---: | ---: |",
        ],
    )
    for origin_key, origin_total in summary["by_origin_total"].items():
        role_breakdown = summary["by_origin_and_role"][origin_key]
        lines.append(
            "| "
            f"`{origin_key}` | {origin_total} | "
            f"{role_breakdown[str(RoleEnum.STUDENT)]} | "
            f"{role_breakdown[str(RoleEnum.TEACHER)]} | "
            f"{role_breakdown[str(RoleEnum.ADMIN)]} |"
        )

    lines.extend(
        [
            "",
            "## Methodology",
            "",
        ],
    )
    for origin_key, description in summary["origin_methodology"].items():
        lines.append(f"- `{origin_key}`: {description}")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate user origin audit summary.")
    parser.add_argument(
        "--output-dir",
        default="ops/reports/user-origin-audit",
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
        rows = await _load_user_rows(session)

    summary = _build_summary(rows)
    payload = {
        "generated_at_utc": _iso(generated_at),
        "app_env": str(settings.app_env),
        "summary": summary,
    }

    json_path = output_dir / f"user-origin-audit-{timestamp}.json"
    md_path = output_dir / f"user-origin-audit-{timestamp}.md"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(
        _render_markdown(
            generated_at_utc=generated_at,
            app_env=str(settings.app_env),
            summary=summary,
        ),
        encoding="utf-8",
    )

    print(f"user_origin_audit_json={json_path}")
    print(f"user_origin_audit_markdown={md_path}")
    print("user_origin_audit_status=success")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
