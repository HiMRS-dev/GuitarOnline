"""Identity repository layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import RoleEnum
from app.modules.identity.models import RefreshToken, Role, User, build_default_full_name


class IdentityRepository:
    """DB operations for identity domain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_role_by_name(self, role_name: RoleEnum) -> Role | None:
        stmt = select(Role).where(Role.name == role_name)
        return await self.session.scalar(stmt)

    async def create_role(self, role_name: RoleEnum) -> Role:
        role = Role(name=role_name)
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).options(selectinload(User.role)).where(User.email == email)
        return await self.session.scalar(stmt)

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).options(selectinload(User.role)).where(User.id == user_id)
        return await self.session.scalar(stmt)

    async def create_user(
        self,
        email: str,
        password_hash: str,
        timezone: str,
        role_id: UUID,
    ) -> User:
        user = User(
            email=email,
            full_name=build_default_full_name(email),
            password_hash=password_hash,
            timezone=timezone,
            role_id=role_id,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["role"])
        return user

    async def backfill_missing_full_names(self) -> int:
        """Populate deterministic full names for users with empty profile name."""
        stmt = select(User).where(func.length(func.trim(func.coalesce(User.full_name, ""))) == 0)
        users = list((await self.session.scalars(stmt)).all())
        if not users:
            return 0

        updated_count = 0
        for user in users:
            generated_full_name = build_default_full_name(user.email)
            if not generated_full_name:
                continue
            user.full_name = generated_full_name
            updated_count += 1

        if updated_count > 0:
            await self.session.flush()
        return updated_count

    async def update_user(
        self,
        user: User,
        *,
        full_name: str | None = None,
        age: int | None = None,
        update_age: bool = False,
    ) -> User:
        if full_name is not None:
            user.full_name = full_name
        if update_age:
            user.age = age

        await self.session.flush()
        await self.session.refresh(user, attribute_names=["role"])
        return user

    async def create_refresh_token(
        self,
        user_id: UUID,
        token_id: str,
        expires_at: datetime,
    ) -> RefreshToken:
        refresh_token = RefreshToken(user_id=user_id, token_id=token_id, expires_at=expires_at)
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_refresh_token_by_id(self, token_id: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_id == token_id)
        return await self.session.scalar(stmt)

    async def revoke_refresh_token(self, token_id: str, revoked_at: datetime) -> None:
        token = await self.get_refresh_token_by_id(token_id)
        if token is not None:
            token.revoked_at = revoked_at
            await self.session.flush()
