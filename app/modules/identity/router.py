"""Identity API router."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.core.config import get_settings
from app.modules.identity.rate_limit import (
    enforce_login_rate_limit,
    enforce_refresh_rate_limit,
    enforce_register_rate_limit,
)
from app.modules.identity.schemas import (
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserRead,
)
from app.modules.identity.service import (
    IdentityService,
    get_current_user,
    get_identity_service,
)
from app.shared.exceptions import UnauthorizedException

router = APIRouter(prefix="/identity", tags=["identity"])
settings = get_settings()


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_refresh_cookie_secure,
        samesite=settings.auth_refresh_cookie_samesite,
        domain=settings.auth_refresh_cookie_domain,
        path=settings.auth_refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        domain=settings.auth_refresh_cookie_domain,
        path=settings.auth_refresh_cookie_path,
    )


def _resolve_refresh_token(
    payload: RefreshRequest | None,
    refresh_token_cookie: str | None,
) -> str:
    if payload is not None and payload.refresh_token:
        return payload.refresh_token
    if refresh_token_cookie:
        return refresh_token_cookie
    raise UnauthorizedException("Refresh token is required")


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    _=Depends(enforce_register_rate_limit),
    service: IdentityService = Depends(get_identity_service),
) -> UserRead:
    """Register a new account."""
    user = await service.register(payload)
    return UserRead.model_validate(user)


@router.post("/auth/login", response_model=TokenPair)
async def login(
    response: Response,
    payload: LoginRequest,
    _=Depends(enforce_login_rate_limit),
    service: IdentityService = Depends(get_identity_service),
) -> TokenPair:
    """Sign in by email/password and return JWT token pair."""
    token_pair = await service.login(payload)
    _set_refresh_cookie(response, token_pair.refresh_token)
    return token_pair


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh_tokens(
    response: Response,
    payload: RefreshRequest | None = None,
    refresh_token_cookie: str | None = Cookie(
        default=None,
        alias=settings.auth_refresh_cookie_name,
    ),
    _=Depends(enforce_refresh_rate_limit),
    service: IdentityService = Depends(get_identity_service),
) -> TokenPair:
    """Rotate refresh token and issue new token pair."""
    refresh_token_value = _resolve_refresh_token(payload, refresh_token_cookie)
    token_pair = await service.refresh_tokens(refresh_token_value)
    _set_refresh_cookie(response, token_pair.refresh_token)
    return token_pair


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    payload: RefreshRequest | None = None,
    refresh_token_cookie: str | None = Cookie(
        default=None,
        alias=settings.auth_refresh_cookie_name,
    ),
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Revoke refresh token when present and clear refresh cookie."""
    refresh_token_value = None
    if payload is not None and payload.refresh_token:
        refresh_token_value = payload.refresh_token
    elif refresh_token_cookie:
        refresh_token_value = refresh_token_cookie

    if refresh_token_value:
        await service.revoke_refresh_token(refresh_token_value)
    _clear_refresh_cookie(response)


@router.get("/users/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_user)) -> UserRead:
    """Return profile of authenticated user."""
    return UserRead.model_validate(current_user)
