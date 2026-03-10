"""Seed idempotent demo data for local/non-production environments."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import SessionLocal, close_engine
from app.core.enums import AppEnvEnum, PackageStatusEnum, RoleEnum, TeacherStatusEnum
from app.core.security import hash_password, verify_password
from app.modules.audit.repository import AuditRepository
from app.modules.billing.models import LessonPackage
from app.modules.billing.repository import BillingRepository
from app.modules.billing.schemas import PackageCreate
from app.modules.billing.service import BillingService
from app.modules.identity.models import Role, User
from app.modules.scheduling.models import AvailabilitySlot
from app.modules.scheduling.repository import SchedulingRepository
from app.modules.scheduling.schemas import SlotCreate
from app.modules.scheduling.service import SchedulingService
from app.modules.teachers.models import TeacherProfile

DEMO_PASSWORD = "DemoPass123!"

DEMO_ADMIN_EMAILS = ("demo-admin@guitaronline.dev",)
DEMO_TEACHER_EMAILS = (
    "demo-teacher-1@guitaronline.dev",
    "demo-teacher-2@guitaronline.dev",
    "demo-teacher-3@guitaronline.dev",
)
DEMO_STUDENT_EMAILS = (
    "demo-student-1@guitaronline.dev",
    "demo-student-2@guitaronline.dev",
    "demo-student-3@guitaronline.dev",
    "demo-student-4@guitaronline.dev",
    "demo-student-5@guitaronline.dev",
)

DEMO_SLOT_DAY_OFFSETS = (1, 2, 3, 4, 5)
DEMO_SLOT_START_HOURS = (12, 18)
DEMO_SLOT_DURATION_MINUTES = 60

DEMO_PACKAGE_LESSONS_TOTAL = (10, 16)
DEMO_PACKAGE_EXPIRES_IN_DAYS = 90


@dataclass(slots=True)
class SeedStats:
    roles_created: int = 0
    users_created: int = 0
    users_updated: int = 0
    teacher_profiles_created: int = 0
    teacher_profiles_updated: int = 0
    slots_created: int = 0
    packages_created: int = 0
    package_ids: list[str] = field(default_factory=list)


async def _ensure_roles(session: AsyncSession) -> int:
    created = 0
    for role_name in (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN):
        existing = await session.scalar(select(Role).where(Role.name == role_name))
        if existing is None:
            session.add(Role(name=role_name))
            created += 1
    await session.flush()
    return created


async def _ensure_user(
    session: AsyncSession,
    *,
    email: str,
    role_name: RoleEnum,
    timezone: str,
) -> tuple[User, bool]:
    role = await session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        raise RuntimeError(f"Role {role_name} was not found after ensure_roles")

    user = await session.scalar(
        select(User).options(selectinload(User.role)).where(User.email == email),
    )
    created = False
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            timezone=timezone,
            is_active=True,
            role_id=role.id,
        )
        session.add(user)
        created = True
    else:
        if not verify_password(DEMO_PASSWORD, user.password_hash):
            user.password_hash = hash_password(DEMO_PASSWORD)
        if user.role_id != role.id:
            user.role_id = role.id
        if user.timezone != timezone:
            user.timezone = timezone
        if not user.is_active:
            user.is_active = True

    await session.flush()
    await session.refresh(user, attribute_names=["role"])
    return user, created


async def _ensure_teacher_profile(
    session: AsyncSession,
    *,
    teacher_user: User,
    display_name: str,
    experience_years: int,
) -> bool:
    profile = await session.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == teacher_user.id),
    )
    bio = (
        f"{display_name}. Demo teacher profile for scheduling, booking and reporting flows."
    )
    if profile is None:
        profile = TeacherProfile(
            user_id=teacher_user.id,
            display_name=display_name,
            bio=bio,
            experience_years=experience_years,
            is_approved=True,
            status=TeacherStatusEnum.VERIFIED,
        )
        session.add(profile)
        await session.flush()
        return True

    profile.display_name = display_name
    profile.bio = bio
    profile.experience_years = experience_years
    profile.is_approved = True
    profile.status = TeacherStatusEnum.VERIFIED
    await session.flush()
    return False


def _build_demo_slot_ranges(now: datetime) -> list[tuple[datetime, datetime]]:
    ranges: list[tuple[datetime, datetime]] = []
    for day_offset in DEMO_SLOT_DAY_OFFSETS:
        target_date = (now + timedelta(days=day_offset)).date()
        for hour in DEMO_SLOT_START_HOURS:
            start_at = datetime.combine(target_date, time(hour=hour, tzinfo=UTC))
            end_at = start_at + timedelta(minutes=DEMO_SLOT_DURATION_MINUTES)
            ranges.append((start_at, end_at))
    return ranges


async def _ensure_demo_slots(
    session: AsyncSession,
    *,
    admin_user: User,
    teacher_users: list[User],
) -> int:
    if not teacher_users:
        return 0

    scheduling_service = SchedulingService(
        repository=SchedulingRepository(session),
        audit_repository=AuditRepository(session),
    )
    created = 0
    now = datetime.now(UTC)
    slot_ranges = _build_demo_slot_ranges(now)

    for idx, (start_at, end_at) in enumerate(slot_ranges):
        teacher_user = teacher_users[idx % len(teacher_users)]
        existing = await session.scalar(
            select(AvailabilitySlot).where(
                AvailabilitySlot.teacher_id == teacher_user.id,
                AvailabilitySlot.start_at == start_at,
                AvailabilitySlot.end_at == end_at,
            ),
        )
        if existing is not None:
            continue

        await scheduling_service.create_slot(
            SlotCreate(
                teacher_id=teacher_user.id,
                start_at=start_at,
                end_at=end_at,
            ),
            admin_user,
        )
        created += 1

    await session.flush()
    return created


async def _ensure_student_package(
    session: AsyncSession,
    *,
    admin_user: User,
    student_user: User,
    lessons_total: int,
) -> tuple[LessonPackage, bool]:
    now = datetime.now(UTC)
    existing_active = await session.scalar(
        select(LessonPackage)
        .where(
            LessonPackage.student_id == student_user.id,
            LessonPackage.status == PackageStatusEnum.ACTIVE,
            LessonPackage.expires_at > now,
            LessonPackage.lessons_left > 0,
        )
        .order_by(LessonPackage.created_at.desc()),
    )
    if existing_active is not None:
        return existing_active, False

    billing_service = BillingService(
        repository=BillingRepository(session),
        audit_repository=AuditRepository(session),
    )
    package = await billing_service.create_package(
        PackageCreate(
            student_id=student_user.id,
            lessons_total=lessons_total,
            expires_at=now + timedelta(days=DEMO_PACKAGE_EXPIRES_IN_DAYS),
        ),
        admin_user,
    )
    await session.flush()
    return package, True


async def _run_seed(*, allow_production: bool) -> SeedStats:
    settings = get_settings()
    if settings.app_env is AppEnvEnum.PRODUCTION and not allow_production:
        raise RuntimeError(
            "Refusing to seed demo data in production. "
            "Re-run with --allow-production only if you are absolutely sure.",
        )

    stats = SeedStats()

    async with SessionLocal() as session:
        try:
            stats.roles_created = await _ensure_roles(session)

            admin_users: list[User] = []
            for email in DEMO_ADMIN_EMAILS:
                user, created = await _ensure_user(
                    session,
                    email=email,
                    role_name=RoleEnum.ADMIN,
                    timezone="UTC",
                )
                admin_users.append(user)
                if created:
                    stats.users_created += 1
                else:
                    stats.users_updated += 1

            teacher_users: list[User] = []
            for email in DEMO_TEACHER_EMAILS:
                user, created = await _ensure_user(
                    session,
                    email=email,
                    role_name=RoleEnum.TEACHER,
                    timezone="UTC",
                )
                teacher_users.append(user)
                if created:
                    stats.users_created += 1
                else:
                    stats.users_updated += 1

            student_users: list[User] = []
            for email in DEMO_STUDENT_EMAILS:
                user, created = await _ensure_user(
                    session,
                    email=email,
                    role_name=RoleEnum.STUDENT,
                    timezone="UTC",
                )
                student_users.append(user)
                if created:
                    stats.users_created += 1
                else:
                    stats.users_updated += 1

            for idx, teacher_user in enumerate(teacher_users, start=1):
                created = await _ensure_teacher_profile(
                    session,
                    teacher_user=teacher_user,
                    display_name=f"Demo Guitar Teacher {idx}",
                    experience_years=5 + idx,
                )
                if created:
                    stats.teacher_profiles_created += 1
                else:
                    stats.teacher_profiles_updated += 1

            stats.slots_created = await _ensure_demo_slots(
                session,
                admin_user=admin_users[0],
                teacher_users=teacher_users,
            )

            for idx, lessons_total in enumerate(DEMO_PACKAGE_LESSONS_TOTAL):
                student_user = student_users[idx]
                package, created = await _ensure_student_package(
                    session,
                    admin_user=admin_users[0],
                    student_user=student_user,
                    lessons_total=lessons_total,
                )
                stats.package_ids.append(str(package.id))
                if created:
                    stats.packages_created += 1

            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed idempotent demo data for GuitarOnline: "
            "1 admin, 3 teachers, 5 students, 2 packages, 10 slots."
        ),
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Allow seeding even when APP_ENV is production.",
    )
    return parser


def _print_summary(stats: SeedStats) -> None:
    print("Demo seed completed.")
    print(f"- Roles created: {stats.roles_created}")
    print(f"- Users created: {stats.users_created}")
    print(f"- Users updated: {stats.users_updated}")
    print(f"- Teacher profiles created: {stats.teacher_profiles_created}")
    print(f"- Teacher profiles updated: {stats.teacher_profiles_updated}")
    print(f"- Slots created: {stats.slots_created}")
    print(f"- Packages created: {stats.packages_created}")
    print(f"- Package ids: {stats.package_ids}")
    print("")
    print("Demo credentials (non-production only):")
    print("- admins:")
    for email in DEMO_ADMIN_EMAILS:
        print(f"  - {email} / {DEMO_PASSWORD}")
    print("- teachers:")
    for email in DEMO_TEACHER_EMAILS:
        print(f"  - {email} / {DEMO_PASSWORD}")
    print("- students:")
    for email in DEMO_STUDENT_EMAILS:
        print(f"  - {email} / {DEMO_PASSWORD}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        stats = asyncio.run(_run_seed(allow_production=args.allow_production))
    except Exception as exc:
        print(f"Demo seed failed: {exc}")
        return 1
    finally:
        asyncio.run(close_engine())

    _print_summary(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
