"""Seed idempotent demo data for local/non-production environments."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import SessionLocal, close_engine
from app.core.enums import PackageStatusEnum, RoleEnum
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

DEMO_ADMIN_EMAIL = "demo-admin@guitaronline.dev"
DEMO_TEACHER_EMAIL = "demo-teacher@guitaronline.dev"
DEMO_STUDENT_EMAIL = "demo-student@guitaronline.dev"

DEMO_SLOT_DAY_OFFSETS = (1, 2, 3, 4, 5)
DEMO_SLOT_START_HOURS = (12, 18)
DEMO_SLOT_DURATION_MINUTES = 60

DEMO_PACKAGE_LESSONS_TOTAL = 12
DEMO_PACKAGE_EXPIRES_IN_DAYS = 90


@dataclass(slots=True)
class SeedStats:
    roles_created: int = 0
    users_created: int = 0
    users_updated: int = 0
    teacher_profile_created: bool = False
    slots_created: int = 0
    package_created: bool = False
    package_id: str | None = None


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


async def _ensure_teacher_profile(session: AsyncSession, teacher_user: User) -> bool:
    profile = await session.scalar(
        select(TeacherProfile).where(TeacherProfile.user_id == teacher_user.id),
    )
    if profile is None:
        profile = TeacherProfile(
            user_id=teacher_user.id,
            display_name="Demo Guitar Teacher",
            bio=(
                "Преподаватель для демо-сценариев. "
                "Фокус: основы, ритм, аккорды и разбор песен."
            ),
            experience_years=8,
            is_approved=True,
        )
        session.add(profile)
        await session.flush()
        return True

    profile.display_name = "Demo Guitar Teacher"
    profile.bio = (
        "Преподаватель для демо-сценариев. "
        "Фокус: основы, ритм, аккорды и разбор песен."
    )
    profile.experience_years = 8
    profile.is_approved = True
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
    teacher_user: User,
) -> int:
    scheduling_service = SchedulingService(SchedulingRepository(session))
    created = 0
    now = datetime.now(UTC)

    for start_at, end_at in _build_demo_slot_ranges(now):
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
            lessons_total=DEMO_PACKAGE_LESSONS_TOTAL,
            expires_at=now + timedelta(days=DEMO_PACKAGE_EXPIRES_IN_DAYS),
        ),
        admin_user,
    )
    await session.flush()
    return package, True


async def _run_seed(*, allow_production: bool) -> SeedStats:
    settings = get_settings()
    app_env = settings.app_env.strip().lower()
    if app_env in {"production", "prod"} and not allow_production:
        raise RuntimeError(
            "Refusing to seed demo data in production. "
            "Re-run with --allow-production only if you are absolutely sure.",
        )

    stats = SeedStats()

    async with SessionLocal() as session:
        try:
            stats.roles_created = await _ensure_roles(session)

            admin_user, admin_created = await _ensure_user(
                session,
                email=DEMO_ADMIN_EMAIL,
                role_name=RoleEnum.ADMIN,
                timezone="UTC",
            )
            teacher_user, teacher_created = await _ensure_user(
                session,
                email=DEMO_TEACHER_EMAIL,
                role_name=RoleEnum.TEACHER,
                timezone="UTC",
            )
            student_user, student_created = await _ensure_user(
                session,
                email=DEMO_STUDENT_EMAIL,
                role_name=RoleEnum.STUDENT,
                timezone="UTC",
            )

            stats.users_created = sum([admin_created, teacher_created, student_created])
            stats.users_updated = 3 - stats.users_created

            stats.teacher_profile_created = await _ensure_teacher_profile(session, teacher_user)
            stats.slots_created = await _ensure_demo_slots(
                session,
                admin_user=admin_user,
                teacher_user=teacher_user,
            )
            package, package_created = await _ensure_student_package(
                session,
                admin_user=admin_user,
                student_user=student_user,
            )
            stats.package_created = package_created
            stats.package_id = str(package.id)

            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed idempotent demo data for GuitarOnline (users, teacher profile, "
            "open slots, active student package)."
        ),
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Allow seeding even when APP_ENV is production/prod.",
    )
    return parser


def _print_summary(stats: SeedStats) -> None:
    print("Demo seed completed.")
    print(f"- Roles created: {stats.roles_created}")
    print(f"- Users created: {stats.users_created}")
    print(f"- Users updated: {stats.users_updated}")
    print(f"- Teacher profile created: {stats.teacher_profile_created}")
    print(f"- Slots created: {stats.slots_created}")
    print(f"- Student active package created: {stats.package_created}")
    print(f"- Student active package id: {stats.package_id}")
    print("")
    print("Demo credentials (non-production only):")
    print(f"- admin:   {DEMO_ADMIN_EMAIL} / {DEMO_PASSWORD}")
    print(f"- teacher: {DEMO_TEACHER_EMAIL} / {DEMO_PASSWORD}")
    print(f"- student: {DEMO_STUDENT_EMAIL} / {DEMO_PASSWORD}")


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
