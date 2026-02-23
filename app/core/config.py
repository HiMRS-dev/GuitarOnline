"""Application settings loaded from environment."""

from functools import lru_cache

from pydantic import Field, model_validator
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

    @model_validator(mode="after")
    def validate_secret_key_for_environment(self) -> "Settings":
        """Block default secret key in production-like environments."""
        env_name = self.app_env.strip().lower()
        if env_name in {"production", "prod"} and self.secret_key == "change-me":
            raise ValueError("SECRET_KEY must not use the default value in production environment")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
