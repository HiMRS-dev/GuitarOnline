"""Application settings loaded from environment."""

from collections.abc import Sequence
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.enums import AppEnvEnum, RoleEnum


class Settings(BaseSettings):
    """Runtime application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "GuitarOnline"
    app_env: AppEnvEnum = Field(...)
    debug: bool = False
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    secret_key: str = Field(default="change-me", min_length=8)
    jwt_secret: str | None = Field(default=None, min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/guitaronline"
    frontend_admin_origin: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:5173",)
    kpi_excluded_email_prefixes: Annotated[tuple[str, ...], NoDecode] = ("synthetic-ops-",)

    booking_hold_minutes: int = 10
    booking_refund_window_hours: int = 24
    slot_min_duration_minutes: int = 30
    slot_bulk_create_max_slots: int = 1000
    lesson_meeting_url_template: str | None = None

    redis_url: str | None = None

    auth_rate_limit_window_seconds: int = 60
    auth_rate_limit_register_requests: int = 5
    auth_rate_limit_login_requests: int = 10
    auth_rate_limit_refresh_requests: int = 20
    auth_rate_limit_backend: Literal["memory", "redis"] = "memory"
    auth_rate_limit_redis_namespace: str = "auth_rate_limit"
    auth_refresh_cookie_name: str = "go_refresh_token"
    auth_refresh_cookie_secure: bool = False
    auth_refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_refresh_cookie_domain: str | None = None
    auth_refresh_cookie_path: str = "/api/v1/identity/auth"
    auth_register_allowed_roles: Annotated[tuple[RoleEnum, ...], NoDecode] = (RoleEnum.STUDENT,)
    auth_rate_limit_trusted_proxy_ips: Annotated[tuple[str, ...], NoDecode] = (
        "127.0.0.1",
        "::1",
    )
    auth_rate_limit_allow_in_memory_in_production: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_flag(cls, value: object) -> object:
        """Normalize common environment aliases for debug flag."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: object) -> object:
        """Normalize legacy aliases into strict runtime environment enum values."""
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        aliases = {
            "dev": "development",
            "development": "development",
            "test": "test",
            "testing": "test",
            "stage": "staging",
            "staging": "staging",
            "prod": "production",
            "production": "production",
        }
        return aliases.get(normalized, normalized)

    @field_validator("auth_rate_limit_backend", mode="before")
    @classmethod
    def normalize_rate_limit_backend(cls, value: object) -> object:
        """Normalize backend token for case-insensitive env parsing."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("auth_refresh_cookie_samesite", mode="before")
    @classmethod
    def normalize_refresh_cookie_samesite(cls, value: object) -> object:
        """Normalize refresh-cookie SameSite value for env parsing."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("auth_rate_limit_trusted_proxy_ips", mode="before")
    @classmethod
    def parse_trusted_proxy_ips(cls, value: object) -> tuple[str, ...]:
        """Parse trusted proxy IPs from comma-separated env value."""
        if value is None:
            return ()
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        if isinstance(value, Sequence):
            return tuple(str(item).strip() for item in value if str(item).strip())
        raise TypeError(
            "AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS must be a comma-separated string or list",
        )

    @field_validator("auth_register_allowed_roles", mode="before")
    @classmethod
    def parse_auth_register_allowed_roles(cls, value: object) -> tuple[RoleEnum, ...]:
        """Parse self-registration role allowlist from env value."""
        if value is None:
            return (RoleEnum.STUDENT,)

        if isinstance(value, str):
            raw_items: Sequence[object] = value.split(",")
        elif isinstance(value, Sequence):
            raw_items = value
        else:
            raise TypeError(
                "AUTH_REGISTER_ALLOWED_ROLES must be a comma-separated string or list",
            )

        roles: list[RoleEnum] = []
        for raw_item in raw_items:
            normalized = str(raw_item).strip().lower()
            if not normalized:
                continue
            try:
                role = RoleEnum(normalized)
            except ValueError as exc:
                raise ValueError(
                    f"Unsupported role in AUTH_REGISTER_ALLOWED_ROLES: {raw_item}",
                ) from exc
            roles.append(role)

        if not roles:
            raise ValueError("AUTH_REGISTER_ALLOWED_ROLES must include at least one role")

        return tuple(roles)

    @field_validator("frontend_admin_origin", mode="before")
    @classmethod
    def parse_frontend_admin_origin(cls, value: object) -> tuple[str, ...]:
        """Parse allowed admin frontend origins from env value."""
        if value is None:
            return ("http://localhost:5173",)
        if isinstance(value, str):
            origins = tuple(item.strip() for item in value.split(",") if item.strip())
            return origins or ("http://localhost:5173",)
        if isinstance(value, Sequence):
            origins = tuple(str(item).strip() for item in value if str(item).strip())
            return origins or ("http://localhost:5173",)
        raise TypeError(
            "FRONTEND_ADMIN_ORIGIN must be a comma-separated string or list",
        )

    @field_validator("kpi_excluded_email_prefixes", mode="before")
    @classmethod
    def parse_kpi_excluded_email_prefixes(cls, value: object) -> tuple[str, ...]:
        """Parse KPI excluded email prefixes from env value."""
        if value is None:
            return ("synthetic-ops-",)
        if isinstance(value, str):
            prefixes = tuple(item.strip() for item in value.split(",") if item.strip())
            return prefixes or ("synthetic-ops-",)
        if isinstance(value, Sequence):
            prefixes = tuple(str(item).strip() for item in value if str(item).strip())
            return prefixes or ("synthetic-ops-",)
        raise TypeError(
            "KPI_EXCLUDED_EMAIL_PREFIXES must be a comma-separated string or list",
        )

    @model_validator(mode="after")
    def validate_security_for_environment(self) -> "Settings":
        """Block unsafe defaults in production-like environments."""
        if self.jwt_secret and self.jwt_secret.strip():
            self.secret_key = self.jwt_secret.strip()

        if self.auth_rate_limit_backend == "redis" and not self.redis_url:
            raise ValueError("REDIS_URL must be set when AUTH_RATE_LIMIT_BACKEND=redis")

        if self.auth_refresh_cookie_samesite == "none" and not self.auth_refresh_cookie_secure:
            raise ValueError(
                "AUTH_REFRESH_COOKIE_SECURE must be true when AUTH_REFRESH_COOKIE_SAMESITE=none",
            )

        if self.app_env is not AppEnvEnum.PRODUCTION:
            return self

        secret_value = self.secret_key.strip().lower()
        if secret_value.startswith("change-me"):
            raise ValueError(
                "SECRET_KEY must not use placeholder values (change-me*) in production environment",
            )

        if (
            self.auth_rate_limit_backend == "memory"
            and not self.auth_rate_limit_allow_in_memory_in_production
        ):
            raise ValueError(
                "AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION must be true in production "
                "when using in-memory auth rate limiting",
            )
        if not self.auth_refresh_cookie_secure:
            raise ValueError("AUTH_REFRESH_COOKIE_SECURE must be true in production environment")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
