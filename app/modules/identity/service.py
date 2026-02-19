"""Identity business logic layer."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.enums import RoleEnum
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    oauth2_scheme,
    verify_password,
)
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.schemas import LoginRequest, TokenPair, UserCreate
from app.shared.exceptions import ConflictException, NotFoundException, UnauthorizedException
from app.shared.utils import utc_now

settings = get_settings()


class IdentityService:
    """Identity domain service."""

    def __init__(self, repository: IdentityRepository) -> None:
        self.repository = repository

    async def ensure_default_roles(self) -> None:
        """Ensure all default roles exist."""
        for role_name in (RoleEnum.STUDENT, RoleEnum.TEACHER, RoleEnum.ADMIN):
            role = await self.repository.get_role_by_name(role_name)
            if role is None:
                await self.repository.create_role(role_name)

    async def register(self, payload: UserCreate) -> User:
        """Register new user."""
        existing_user = await self.repository.get_user_by_email(payload.email)
        if existing_user is not None:
            raise ConflictException("User with this email already exists")

        role = await self.repository.get_role_by_name(payload.role)
        if role is None:
            raise NotFoundException("Role not found")

        password_hash = hash_password(payload.password)
        user = await self.repository.create_user(
            email=payload.email,
            password_hash=password_hash,
            timezone=payload.timezone,
            role_id=role.id,
        )
        return user

    async def login(self, payload: LoginRequest) -> TokenPair:
        """Authenticate user and issue JWT tokens."""
        user = await self.repository.get_user_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedException("Invalid credentials")

        if not user.is_active:
            raise UnauthorizedException("User is inactive")

        token_id = str(uuid4())
        access_token = create_access_token(subject=str(user.id), role=user.role.name)
        refresh_token = create_refresh_token(subject=str(user.id), token_id=token_id, role=user.role.name)

        expires_at = utc_now() + timedelta(days=settings.refresh_token_expire_days)
        await self.repository.create_refresh_token(user.id, token_id, expires_at)

        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def refresh_tokens(self, refresh_token_value: str) -> TokenPair:
        """Rotate refresh token and issue new token pair."""
        payload = decode_token(refresh_token_value)
        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type")

        token_id = payload.get("jti")
        subject = payload.get("sub")
        if not token_id or not subject:
            raise UnauthorizedException("Invalid refresh token")

        db_token = await self.repository.get_refresh_token_by_id(token_id)
        if db_token is None or db_token.revoked_at is not None or db_token.expires_at <= utc_now():
            raise UnauthorizedException("Refresh token is not valid")

        await self.repository.revoke_refresh_token(token_id, utc_now())

        user = await self.repository.get_user_by_id(UUID(subject))
        if user is None or not user.is_active:
            raise UnauthorizedException("User is not valid")

        new_token_id = str(uuid4())
        access_token = create_access_token(subject=str(user.id), role=user.role.name)
        refresh_token = create_refresh_token(subject=str(user.id), token_id=new_token_id, role=user.role.name)
        expires_at = utc_now() + timedelta(days=settings.refresh_token_expire_days)
        await self.repository.create_refresh_token(user.id, new_token_id, expires_at)

        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def get_user_from_access_token(self, token: str) -> User:
        """Resolve user from access token."""
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedException("Invalid access token")

        subject = payload.get("sub")
        if not subject:
            raise UnauthorizedException("Token subject is missing")

        user = await self.repository.get_user_by_id(UUID(subject))
        if user is None:
            raise UnauthorizedException("User not found")
        if not user.is_active:
            raise UnauthorizedException("User is inactive")

        return user


async def get_identity_service(session: AsyncSession = Depends(get_db_session)) -> IdentityService:
    """Dependency to provide identity service."""
    return IdentityService(IdentityRepository(session))


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    service: IdentityService = Depends(get_identity_service),
) -> User:
    """Resolve currently authenticated user from bearer token."""
    return await service.get_user_from_access_token(token)


def require_roles(*roles: RoleEnum):
    """Dependency factory for role-based access."""

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for your role",
            )
        return current_user

    return _checker
