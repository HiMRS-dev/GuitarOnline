#!/usr/bin/env python3
"""Retention cleanup for old synthetic operational check data."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, close_engine
from app.core.enums import BookingStatusEnum, RoleEnum
from app.modules.billing.models import LessonPackage
from app.modules.booking.models import Booking
from app.modules.identity.models import Role, User
from app.modules.scheduling.models import AvailabilitySlot

DEFAULT_RETENTION_DAYS = 14
DEFAULT_EMAIL_PREFIXES = "synthetic-ops-"


@dataclass(frozen=True)
class SyntheticScope:
    all_user_ids: tuple[UUID, ...]
    teacher_user_ids: tuple[UUID, ...]
    student_user_ids: tuple[UUID, ...]
    matched_emails: tuple[str, ...]


@dataclass(frozen=True)
class RetentionResult:
    dry_run: bool
    cutoff_utc: datetime
    scope_user_count: int
    scope_teacher_count: int
    scope_student_count: int
    matched_emails: tuple[str, ...]
    bookings_candidates: int
    slots_candidates: int
    packages_candidates: int
    bookings_deleted: int
    slots_deleted: int
    packages_deleted: int


def _parse_email_prefixes(raw: str) -> tuple[str, ...]:
    prefixes = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    if not prefixes:
        raise ValueError("--email-prefixes must contain at least one non-empty prefix")
    return prefixes


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value, got: {value}")


def _synthetic_email_filters(prefixes: tuple[str, ...]) -> list[object]:
    return [func.lower(User.email).like(f"{prefix}%") for prefix in prefixes]


async def _load_synthetic_scope(
    session: AsyncSession,
    *,
    email_prefixes: tuple[str, ...],
) -> SyntheticScope:
    stmt = (
        select(User.id, User.email, Role.name)
        .join(Role, Role.id == User.role_id)
        .where(or_(*_synthetic_email_filters(email_prefixes)))
    )
    rows = (await session.execute(stmt)).all()

    all_ids: set[UUID] = set()
    teacher_ids: set[UUID] = set()
    student_ids: set[UUID] = set()
    emails: set[str] = set()
    for row in rows:
        user_id = row.id
        role_name = row.name
        all_ids.add(user_id)
        emails.add(str(row.email))
        if role_name == RoleEnum.TEACHER:
            teacher_ids.add(user_id)
        if role_name == RoleEnum.STUDENT:
            student_ids.add(user_id)

    return SyntheticScope(
        all_user_ids=tuple(all_ids),
        teacher_user_ids=tuple(teacher_ids),
        student_user_ids=tuple(student_ids),
        matched_emails=tuple(sorted(emails)),
    )


def _booking_retention_filters(scope: SyntheticScope, cutoff_utc: datetime) -> tuple[object, ...]:
    return (
        or_(
            Booking.student_id.in_(scope.all_user_ids),
            Booking.teacher_id.in_(scope.all_user_ids),
        ),
        Booking.created_at < cutoff_utc,
        Booking.status.in_((BookingStatusEnum.CANCELED, BookingStatusEnum.EXPIRED)),
    )


def _slot_retention_filters(scope: SyntheticScope, cutoff_utc: datetime) -> tuple[object, ...]:
    slot_has_bookings = select(Booking.id).where(Booking.slot_id == AvailabilitySlot.id).exists()
    return (
        AvailabilitySlot.teacher_id.in_(scope.teacher_user_ids),
        AvailabilitySlot.start_at < cutoff_utc,
        ~slot_has_bookings,
    )


def _package_retention_filters(scope: SyntheticScope, cutoff_utc: datetime) -> tuple[object, ...]:
    package_has_bookings = select(Booking.id).where(Booking.package_id == LessonPackage.id).exists()
    return (
        LessonPackage.student_id.in_(scope.student_user_ids),
        LessonPackage.created_at < cutoff_utc,
        ~package_has_bookings,
    )


async def _count_retention_candidates(
    session: AsyncSession,
    *,
    scope: SyntheticScope,
    cutoff_utc: datetime,
) -> tuple[int, int, int]:
    bookings_count = 0
    slots_count = 0
    packages_count = 0

    if scope.all_user_ids:
        bookings_count = int(
            (
                await session.scalar(
                    select(func.count(Booking.id)).where(
                        *_booking_retention_filters(scope, cutoff_utc),
                    ),
                )
            )
            or 0,
        )

    if scope.teacher_user_ids:
        slots_count = int(
            (
                await session.scalar(
                    select(func.count(AvailabilitySlot.id)).where(
                        *_slot_retention_filters(scope, cutoff_utc),
                    ),
                )
            )
            or 0,
        )

    if scope.student_user_ids:
        packages_count = int(
            (
                await session.scalar(
                    select(func.count(LessonPackage.id)).where(
                        *_package_retention_filters(scope, cutoff_utc),
                    ),
                )
            )
            or 0,
        )

    return bookings_count, slots_count, packages_count


async def _delete_retention_data(
    session: AsyncSession,
    *,
    scope: SyntheticScope,
    cutoff_utc: datetime,
) -> tuple[int, int, int]:
    deleted_bookings = 0
    deleted_slots = 0
    deleted_packages = 0

    if scope.all_user_ids:
        deleted_booking_ids = (
            await session.scalars(
                delete(Booking)
                .where(*_booking_retention_filters(scope, cutoff_utc))
                .returning(Booking.id),
            )
        ).all()
        deleted_bookings = len(deleted_booking_ids)

    if scope.teacher_user_ids:
        deleted_slot_ids = (
            await session.scalars(
                delete(AvailabilitySlot)
                .where(*_slot_retention_filters(scope, cutoff_utc))
                .returning(AvailabilitySlot.id),
            )
        ).all()
        deleted_slots = len(deleted_slot_ids)

    if scope.student_user_ids:
        deleted_package_ids = (
            await session.scalars(
                delete(LessonPackage)
                .where(*_package_retention_filters(scope, cutoff_utc))
                .returning(LessonPackage.id),
            )
        ).all()
        deleted_packages = len(deleted_package_ids)

    return deleted_bookings, deleted_slots, deleted_packages


async def run_retention(
    *,
    retention_days: int,
    email_prefixes: tuple[str, ...],
    dry_run: bool,
) -> RetentionResult:
    if retention_days <= 0:
        raise ValueError("--retention-days must be greater than 0")

    cutoff_utc = datetime.now(UTC) - timedelta(days=retention_days)

    async with SessionLocal() as session:
        try:
            scope = await _load_synthetic_scope(session, email_prefixes=email_prefixes)
            bookings_candidates, slots_candidates, packages_candidates = (
                await _count_retention_candidates(
                    session,
                    scope=scope,
                    cutoff_utc=cutoff_utc,
                )
            )

            bookings_deleted = 0
            slots_deleted = 0
            packages_deleted = 0
            if not dry_run and scope.all_user_ids:
                bookings_deleted, slots_deleted, packages_deleted = await _delete_retention_data(
                    session,
                    scope=scope,
                    cutoff_utc=cutoff_utc,
                )
                await session.commit()
            else:
                await session.rollback()
        except Exception:
            await session.rollback()
            raise

    return RetentionResult(
        dry_run=dry_run,
        cutoff_utc=cutoff_utc,
        scope_user_count=len(scope.all_user_ids),
        scope_teacher_count=len(scope.teacher_user_ids),
        scope_student_count=len(scope.student_user_ids),
        matched_emails=scope.matched_emails,
        bookings_candidates=bookings_candidates,
        slots_candidates=slots_candidates,
        packages_candidates=packages_candidates,
        bookings_deleted=bookings_deleted,
        slots_deleted=slots_deleted,
        packages_deleted=packages_deleted,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Cleanup old synthetic ops data from DB: canceled/expired synthetic bookings, "
            "orphan synthetic slots, and orphan synthetic packages."
        ),
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.getenv("SYNTHETIC_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS))),
        help="Delete records older than this many days (default: 14).",
    )
    parser.add_argument(
        "--email-prefixes",
        default=os.getenv("SYNTHETIC_RETENTION_EMAIL_PREFIXES", DEFAULT_EMAIL_PREFIXES),
        help="Comma-separated synthetic email prefixes (default: synthetic-ops-).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=_env_bool("SYNTHETIC_RETENTION_DRY_RUN", False),
        help="Report affected records without deleting anything.",
    )
    return parser


async def _async_main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    prefixes = _parse_email_prefixes(args.email_prefixes)
    result = await run_retention(
        retention_days=args.retention_days,
        email_prefixes=prefixes,
        dry_run=args.dry_run,
    )

    print(
        "Synthetic retention completed "
        f"(dry_run={result.dry_run}, cutoff_utc={result.cutoff_utc.isoformat()})",
    )
    print(
        "Scope: "
        f"users={result.scope_user_count}, "
        f"teachers={result.scope_teacher_count}, "
        f"students={result.scope_student_count}",
    )
    if result.matched_emails:
        print(f"Matched synthetic emails: {', '.join(result.matched_emails)}")
    else:
        print("Matched synthetic emails: none")

    if result.dry_run:
        print(
            "Candidates: "
            f"bookings={result.bookings_candidates}, "
            f"slots={result.slots_candidates}, "
            f"packages={result.packages_candidates}",
        )
    else:
        print(
            "Deleted: "
            f"bookings={result.bookings_deleted}, "
            f"slots={result.slots_deleted}, "
            f"packages={result.packages_deleted}",
        )

    print(
        json.dumps(
            {
                "dry_run": result.dry_run,
                "cutoff_utc": result.cutoff_utc.isoformat(),
                "scope_user_count": result.scope_user_count,
                "scope_teacher_count": result.scope_teacher_count,
                "scope_student_count": result.scope_student_count,
                "bookings_candidates": result.bookings_candidates,
                "slots_candidates": result.slots_candidates,
                "packages_candidates": result.packages_candidates,
                "bookings_deleted": result.bookings_deleted,
                "slots_deleted": result.slots_deleted,
                "packages_deleted": result.packages_deleted,
            },
            sort_keys=True,
        ),
    )
    return 0


def main() -> int:
    try:
        return asyncio.run(_async_main())
    finally:
        try:
            asyncio.run(close_engine())
        except RuntimeError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
