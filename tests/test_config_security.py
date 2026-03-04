from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_secret_key_allowed_in_development() -> None:
    settings = Settings(_env_file=None, app_env="development", secret_key="change-me")
    assert settings.secret_key == "change-me"


def test_default_secret_key_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", secret_key="change-me")


def test_placeholder_secret_key_prefix_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="change-me-in-production",
            auth_rate_limit_allow_in_memory_in_production=True,
        )


def test_in_memory_rate_limiter_requires_explicit_ack_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", secret_key="super-secure-value")


def test_custom_secret_key_allowed_in_production_with_explicit_ack() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        secret_key="super-secure-value",
        auth_rate_limit_allow_in_memory_in_production=True,
    )
    assert settings.secret_key == "super-secure-value"


def test_redis_backend_requires_redis_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="super-secure-value",
            auth_rate_limit_backend="redis",
            redis_url=None,
        )


def test_redis_backend_allows_production_without_in_memory_ack() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        secret_key="super-secure-value",
        auth_rate_limit_backend="redis",
        redis_url="redis://redis:6379/0",
    )
    assert settings.auth_rate_limit_backend == "redis"


def test_jwt_secret_alias_overrides_secret_key() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        secret_key="primary-secret",
        jwt_secret="jwt-priority-secret",
    )
    assert settings.secret_key == "jwt-priority-secret"


def test_frontend_admin_origin_parsing_from_comma_string() -> None:
    settings = Settings(
        _env_file=None,
        frontend_admin_origin="http://localhost:5173,https://admin.guitaronline.dev",
    )
    assert settings.frontend_admin_origin == (
        "http://localhost:5173",
        "https://admin.guitaronline.dev",
    )


def test_debug_release_alias_is_parsed_as_false() -> None:
    settings = Settings(_env_file=None, debug="release")
    assert settings.debug is False


def test_debug_development_alias_is_parsed_as_true() -> None:
    settings = Settings(_env_file=None, debug="development")
    assert settings.debug is True
