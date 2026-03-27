"""Create or update a bootstrap admin account for non-production environments."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.database import SessionLocal, close_engine
from app.core.enums import AppEnvEnum, RoleEnum
from app.core.security import hash_password
from app.modules.identity.models import Role, User, build_default_full_name


async def _ensure_roles() -> None:
    async with SessionLocal() as session:
        try:
            for role_name in (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN):
                existing = await session.scalar(select(Role).where(Role.name == role_name))
                if existing is None:
                    session.add(Role(name=role_name))
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _bootstrap_admin(*, email: str, password: str, timezone: str) -> str:
    async with SessionLocal() as session:
        try:
            role = await session.scalar(select(Role).where(Role.name == RoleEnum.ADMIN))
            if role is None:
                raise RuntimeError("Admin role is missing after ensure_roles")

            user = await session.scalar(
                select(User).options(selectinload(User.role)).where(User.email == email),
            )
            if user is None:
                user = User(
                    email=email,
                    full_name=build_default_full_name(email),
                    password_hash=hash_password(password),
                    timezone=timezone,
                    is_active=True,
                    role_id=role.id,
                )
                session.add(user)
                result = "created"
            else:
                if not user.full_name.strip():
                    user.full_name = build_default_full_name(email)
                user.password_hash = hash_password(password)
                user.timezone = timezone
                user.is_active = True
                user.role_id = role.id
                result = "updated"

            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def _run_bootstrap(*, email: str, password: str, timezone: str) -> str:
    try:
        await _ensure_roles()
        return await _bootstrap_admin(
            email=email,
            password=password,
            timezone=timezone,
        )
    finally:
        await close_engine()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or update a bootstrap admin account from environment variables.",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Allow execution when APP_ENV=production.",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip(),
        help="Bootstrap admin email (defaults to BOOTSTRAP_ADMIN_EMAIL).",
    )
    parser.add_argument(
        "--timezone",
        default=os.getenv("BOOTSTRAP_ADMIN_TIMEZONE", "UTC").strip() or "UTC",
        help="Bootstrap admin timezone (defaults to BOOTSTRAP_ADMIN_TIMEZONE or UTC).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    settings = get_settings()
    if settings.app_env is AppEnvEnum.PRODUCTION and not args.allow_production:
        print(
            "Refusing to bootstrap admin in production. "
            "Re-run with --allow-production only if this is intentional.",
        )
        return 1

    email = args.email.strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    timezone = args.timezone.strip() or "UTC"

    if not email:
        print("BOOTSTRAP_ADMIN_EMAIL is required.")
        return 1
    if not password:
        print("BOOTSTRAP_ADMIN_PASSWORD is required.")
        return 1

    try:
        result = asyncio.run(
            _run_bootstrap(
                email=email,
                password=password,
                timezone=timezone,
            ),
        )
    except Exception as exc:
        print(f"Bootstrap admin failed: {exc}")
        return 1

    print(f"Bootstrap admin {result}: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
