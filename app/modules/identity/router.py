"""Identity API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.modules.identity.schemas import LoginRequest, RefreshRequest, TokenPair, UserCreate, UserRead
from app.modules.identity.service import IdentityService, get_current_user, get_identity_service

router = APIRouter(prefix="/identity", tags=["identity"])


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    service: IdentityService = Depends(get_identity_service),
) -> UserRead:
    """Register a new account."""
    user = await service.register(payload)
    return UserRead.model_validate(user)


@router.post("/auth/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    service: IdentityService = Depends(get_identity_service),
) -> TokenPair:
    """Sign in by email/password and return JWT token pair."""
    return await service.login(payload)


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh_tokens(
    payload: RefreshRequest,
    service: IdentityService = Depends(get_identity_service),
) -> TokenPair:
    """Rotate refresh token and issue new token pair."""
    return await service.refresh_tokens(payload.refresh_token)


@router.get("/users/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_user)) -> UserRead:
    """Return profile of authenticated user."""
    return UserRead.model_validate(current_user)
