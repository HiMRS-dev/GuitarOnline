"""Application settings loaded from environment."""

from collections.abc import Sequence
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "GuitarOnline"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/guitaronline"

    booking_hold_minutes: int = 10
    booking_refund_window_hours: int = 24

    redis_url: str | None = None

    auth_rate_limit_window_seconds: int = 60
    auth_rate_limit_register_requests: int = 5
    auth_rate_limit_login_requests: int = 10
    auth_rate_limit_refresh_requests: int = 20
    auth_rate_limit_backend: Literal["memory", "redis"] = "memory"
    auth_rate_limit_redis_namespace: str = "auth_rate_limit"
    auth_rate_limit_trusted_proxy_ips: tuple[str, ...] = ("127.0.0.1", "::1")
    auth_rate_limit_allow_in_memory_in_production: bool = False

    @field_validator("auth_rate_limit_backend", mode="before")
    @classmethod
    def normalize_rate_limit_backend(cls, value: object) -> object:
        """Normalize backend token for case-insensitive env parsing."""
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

    @model_validator(mode="after")
    def validate_security_for_environment(self) -> "Settings":
        """Block unsafe defaults in production-like environments."""
        env_name = self.app_env.strip().lower()

        if self.auth_rate_limit_backend == "redis" and not self.redis_url:
            raise ValueError("REDIS_URL must be set when AUTH_RATE_LIMIT_BACKEND=redis")

        if env_name not in {"production", "prod"}:
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
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
