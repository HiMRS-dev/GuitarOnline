# ruff: noqa: E402
"""Reset reusable smoke-pool accounts inside the isolated test contour."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

_repo_root = (
    Path(__file__).resolve().parents[1]
    if "__file__" in globals()
    else Path.cwd()
)
sys.path.insert(0, str(_repo_root))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.enums import AppEnvEnum, RoleEnum, TeacherStatusEnum
from app.core.security import hash_password
from app.modules.admin.models import AdminAction
from app.modules.audit.models import OutboxEvent
from app.modules.billing.models import LessonPackage, Payment
from app.modules.booking.models import Booking
from app.modules.identity.models import RefreshToken, Role, User
from app.modules.lessons.models import Lesson
from app.modules.notifications.models import Notification
from app.modules.scheduling.models import AvailabilitySlot
from app.modules.teachers.models import TeacherProfile, TeacherProfileTag

DEFAULT_SMOKE_POOL_PASSWORD = "StrongPass123!"


@dataclass(frozen=True)
class SmokePoolUserConfig:
    key: str
    email: str
    role: RoleEnum
    display_name: str | None = None


@dataclass(frozen=True)
class SmokePoolResetStats:
    users_created: int
    users_updated: int
    refresh_tokens_deleted: int
    notifications_deleted: int
    admin_actions_deleted: int
    lessons_deleted: int
    bookings_deleted: int
    slots_deleted: int
    payments_deleted: int
    packages_deleted: int
    outbox_events_deleted: int


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reset fixed smoke-pool users in the isolated test contour and clear "
            "their generated business artifacts."
        ),
    )
    parser.add_argument(
        "--allow-non-test",
        action="store_true",
        help="Allow execution when APP_ENV is not test.",
    )
    return parser


def _user_configs() -> tuple[SmokePoolUserConfig, ...]:
    return (
        SmokePoolUserConfig(
            key="admin",
            email=os.getenv("TEST_SMOKE_ADMIN_EMAIL", "smoke-admin-1@guitaronline.dev").strip(),
            role=RoleEnum.ADMIN,
        ),
        SmokePoolUserConfig(
            key="teacher",
            email=os.getenv("TEST_SMOKE_TEACHER_EMAIL", "smoke-teacher-1@guitaronline.dev").strip(),
            role=RoleEnum.TEACHER,
            display_name="Smoke Teacher 1",
        ),
        SmokePoolUserConfig(
            key="student",
            email=os.getenv("TEST_SMOKE_STUDENT_EMAIL", "smoke-student-1@guitaronline.dev").strip(),
            role=RoleEnum.STUDENT,
        ),
        SmokePoolUserConfig(
            key="student_two",
            email=os.getenv(
                "TEST_SMOKE_STUDENT_TWO_EMAIL",
                "smoke-student-2@guitaronline.dev",
            ).strip(),
            role=RoleEnum.STUDENT,
        ),
    )


async def _ensure_roles(session: AsyncSession) -> dict[RoleEnum, Role]:
    roles_by_name: dict[RoleEnum, Role] = {}
    for role_name in (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN):
        role = await session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name)
            session.add(role)
            await session.flush()
        roles_by_name[role_name] = role
    return roles_by_name


async def _upsert_user(
    session: AsyncSession,
    *,
    config: SmokePoolUserConfig,
    password_hash: str,
    roles_by_name: dict[RoleEnum, Role],
) -> tuple[User, bool]:
    user = await session.scalar(
        select(User)
        .options(selectinload(User.role), selectinload(User.teacher_profile))
        .where(User.email == config.email),
    )
    created = False
    role = roles_by_name[config.role]
    if user is None:
        user = User(
            email=config.email,
            password_hash=password_hash,
            timezone="UTC",
            is_active=True,
            role_id=role.id,
        )
        session.add(user)
        await session.flush()
        created = True
    else:
        user.password_hash = password_hash
        user.timezone = "UTC"
        user.is_active = True
        user.role_id = role.id
        user.role = role
        await session.flush()

    return user, created


async def _sync_teacher_profile(
    session: AsyncSession,
    *,
    teacher_user: User,
    display_name: str,
) -> None:
    profile = await session.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == teacher_user.id),
    )
    if profile is None:
        profile = TeacherProfile(
            user_id=teacher_user.id,
            display_name=display_name,
            bio="Reusable smoke-pool teacher for isolated test contour.",
            experience_years=5,
            status=TeacherStatusEnum.ACTIVE,
        )
        session.add(profile)
        await session.flush()
    else:
        profile.display_name = display_name
        profile.bio = "Reusable smoke-pool teacher for isolated test contour."
        profile.experience_years = 5
        profile.status = TeacherStatusEnum.ACTIVE
        await session.flush()

    await session.execute(
        delete(TeacherProfileTag).where(TeacherProfileTag.teacher_profile_id == profile.id),
    )


async def _remove_teacher_profile(session: AsyncSession, *, user_id: UUID) -> None:
    profile_ids = tuple(
        await session.scalars(
            select(TeacherProfile.id).where(TeacherProfile.user_id == user_id),
        ),
    )
    if profile_ids:
        await session.execute(
            delete(TeacherProfileTag).where(TeacherProfileTag.teacher_profile_id.in_(profile_ids)),
        )
        await session.execute(delete(TeacherProfile).where(TeacherProfile.id.in_(profile_ids)))


async def _delete_artifacts(
    session: AsyncSession,
    *,
    admin_user_id: UUID,
    teacher_user_ids: tuple[UUID, ...],
    student_user_ids: tuple[UUID, ...],
) -> SmokePoolResetStats:
    package_ids = tuple(
        await session.scalars(
            select(LessonPackage.id).where(LessonPackage.student_id.in_(student_user_ids)),
        ),
    )
    slot_ids = tuple(
        await session.scalars(
            select(AvailabilitySlot.id).where(AvailabilitySlot.teacher_id.in_(teacher_user_ids)),
        ),
    )
    booking_scope = or_(
        Booking.student_id.in_(student_user_ids),
        Booking.teacher_id.in_(teacher_user_ids),
        Booking.slot_id.in_(slot_ids) if slot_ids else false(),
        Booking.package_id.in_(package_ids) if package_ids else false(),
    )
    booking_ids = tuple(
        await session.scalars(
            select(Booking.id).where(booking_scope),
        ),
    )
    lesson_scope = or_(
        Lesson.student_id.in_(student_user_ids),
        Lesson.teacher_id.in_(teacher_user_ids),
        Lesson.booking_id.in_(booking_ids) if booking_ids else false(),
    )
    lesson_ids = tuple(
        await session.scalars(
            select(Lesson.id).where(lesson_scope),
        ),
    )
    payment_ids = tuple(
        await session.scalars(
            select(Payment.id).where(
                Payment.package_id.in_(package_ids) if package_ids else false(),
            ),
        ),
    )

    refresh_tokens_deleted = len(
        tuple(
            await session.scalars(
                delete(RefreshToken)
                .where(
                    RefreshToken.user_id.in_(
                        (admin_user_id, *teacher_user_ids, *student_user_ids),
                    ),
                )
                .returning(RefreshToken.id),
            ),
        ),
    )
    notifications_deleted = len(
        tuple(
            await session.scalars(
                delete(Notification)
                .where(
                    Notification.user_id.in_(
                        (admin_user_id, *teacher_user_ids, *student_user_ids),
                    ),
                )
                .returning(Notification.id),
            ),
        ),
    )
    admin_actions_deleted = len(
        tuple(
            await session.scalars(
                delete(AdminAction)
                .where(AdminAction.admin_id == admin_user_id)
                .returning(AdminAction.id),
            ),
        ),
    )
    lessons_deleted = len(
        tuple(
            await session.scalars(
                delete(Lesson).where(lesson_scope).returning(Lesson.id),
            ),
        ),
    )
    bookings_deleted = len(
        tuple(
            await session.scalars(
                delete(Booking).where(booking_scope).returning(Booking.id),
            ),
        ),
    )
    slots_deleted = len(
        tuple(
            await session.scalars(
                delete(AvailabilitySlot)
                .where(AvailabilitySlot.teacher_id.in_(teacher_user_ids))
                .returning(AvailabilitySlot.id),
            ),
        ),
    )
    payments_deleted = len(
        tuple(
            await session.scalars(
                delete(Payment)
                .where(
                    Payment.package_id.in_(package_ids)
                    if package_ids
                    else false(),
                )
                .returning(Payment.id),
            ),
        ),
    )
    packages_deleted = len(
        tuple(
            await session.scalars(
                delete(LessonPackage)
                .where(LessonPackage.student_id.in_(student_user_ids))
                .returning(LessonPackage.id),
            ),
        ),
    )

    outbox_target_ids = {
        str(item)
        for item in (
            *lesson_ids,
            *booking_ids,
            *payment_ids,
            *package_ids,
        )
    }
    outbox_events_deleted = 0
    if outbox_target_ids:
        outbox_events_deleted = len(
            tuple(
                await session.scalars(
                    delete(OutboxEvent)
                    .where(OutboxEvent.aggregate_id.in_(tuple(outbox_target_ids)))
                    .returning(OutboxEvent.id),
                ),
            ),
        )

    return SmokePoolResetStats(
        users_created=0,
        users_updated=0,
        refresh_tokens_deleted=refresh_tokens_deleted,
        notifications_deleted=notifications_deleted,
        admin_actions_deleted=admin_actions_deleted,
        lessons_deleted=lessons_deleted,
        bookings_deleted=bookings_deleted,
        slots_deleted=slots_deleted,
        payments_deleted=payments_deleted,
        packages_deleted=packages_deleted,
        outbox_events_deleted=outbox_events_deleted,
    )


async def _run_reset(*, allow_non_test: bool) -> SmokePoolResetStats:
    settings = get_settings()
    if settings.app_env is not AppEnvEnum.TEST and not allow_non_test:
        raise RuntimeError(
            "Refusing to reset smoke pool outside APP_ENV=test. "
            "Re-run with --allow-non-test only if this is intentional.",
        )

    password = os.getenv("TEST_SMOKE_POOL_PASSWORD", DEFAULT_SMOKE_POOL_PASSWORD)
    if not password:
        raise RuntimeError("TEST_SMOKE_POOL_PASSWORD must not be empty.")

    configs = _user_configs()
    if any(not config.email for config in configs):
        raise RuntimeError("Smoke-pool emails must not be empty.")

    password_hash = hash_password(password)

    async with SessionLocal() as session:
        try:
            roles_by_name = await _ensure_roles(session)

            created_count = 0
            updated_count = 0
            users_by_key: dict[str, User] = {}
            for config in configs:
                user, created = await _upsert_user(
                    session,
                    config=config,
                    password_hash=password_hash,
                    roles_by_name=roles_by_name,
                )
                users_by_key[config.key] = user
                if created:
                    created_count += 1
                else:
                    updated_count += 1

            teacher_config = next(config for config in configs if config.key == "teacher")
            await _sync_teacher_profile(
                session,
                teacher_user=users_by_key["teacher"],
                display_name=teacher_config.display_name or "Smoke Teacher 1",
            )
            for config in configs:
                if config.role is RoleEnum.TEACHER:
                    continue
                await _remove_teacher_profile(session, user_id=users_by_key[config.key].id)

            student_user_ids = tuple(
                users_by_key[config.key].id
                for config in configs
                if config.role is RoleEnum.STUDENT
            )
            teacher_user_ids = tuple(
                users_by_key[config.key].id
                for config in configs
                if config.key != "admin"
            )

            stats = await _delete_artifacts(
                session,
                admin_user_id=users_by_key["admin"].id,
                teacher_user_ids=teacher_user_ids,
                student_user_ids=student_user_ids,
            )

            await session.commit()
            return SmokePoolResetStats(
                users_created=created_count,
                users_updated=updated_count,
                refresh_tokens_deleted=stats.refresh_tokens_deleted,
                notifications_deleted=stats.notifications_deleted,
                admin_actions_deleted=stats.admin_actions_deleted,
                lessons_deleted=stats.lessons_deleted,
                bookings_deleted=stats.bookings_deleted,
                slots_deleted=stats.slots_deleted,
                payments_deleted=stats.payments_deleted,
                packages_deleted=stats.packages_deleted,
                outbox_events_deleted=stats.outbox_events_deleted,
            )
        except Exception:
            await session.rollback()
            raise


def _print_summary(stats: SmokePoolResetStats) -> None:
    print("Test smoke pool reset completed.")
    print(f"- Users created: {stats.users_created}")
    print(f"- Users updated: {stats.users_updated}")
    print(f"- Refresh tokens deleted: {stats.refresh_tokens_deleted}")
    print(f"- Notifications deleted: {stats.notifications_deleted}")
    print(f"- Admin actions deleted: {stats.admin_actions_deleted}")
    print(f"- Lessons deleted: {stats.lessons_deleted}")
    print(f"- Bookings deleted: {stats.bookings_deleted}")
    print(f"- Slots deleted: {stats.slots_deleted}")
    print(f"- Payments deleted: {stats.payments_deleted}")
    print(f"- Packages deleted: {stats.packages_deleted}")
    print(f"- Outbox events deleted: {stats.outbox_events_deleted}")
    print("Smoke users:")
    for config in _user_configs():
        print(f"- {config.key} ({config.role}): {config.email}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        stats = asyncio.run(_run_reset(allow_non_test=args.allow_non_test))
    except Exception as exc:
        print(f"Smoke pool reset failed: {exc}")
        return 1

    _print_summary(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
