from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _build_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, app_env="development", **overrides)


def test_app_env_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_app_env_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="sandbox")


def test_legacy_prod_alias_normalized_to_production() -> None:
    settings = Settings(
        _env_file=None,
        app_env="prod",
        secret_key="super-secure-value",
        auth_rate_limit_allow_in_memory_in_production=True,
        auth_refresh_cookie_secure=True,
    )
    assert str(settings.app_env) == "production"


def test_default_secret_key_allowed_in_development() -> None:
    settings = _build_settings(secret_key="change-me")
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
        auth_refresh_cookie_secure=True,
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
        auth_refresh_cookie_secure=True,
    )
    assert settings.auth_rate_limit_backend == "redis"


def test_production_requires_secure_refresh_cookie() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="super-secure-value",
            auth_rate_limit_allow_in_memory_in_production=True,
            auth_refresh_cookie_secure=False,
        )


def test_samesite_none_requires_secure_refresh_cookie() -> None:
    with pytest.raises(ValidationError):
        _build_settings(
            auth_refresh_cookie_samesite="none",
            auth_refresh_cookie_secure=False,
        )


def test_jwt_secret_alias_overrides_secret_key() -> None:
    settings = _build_settings(secret_key="primary-secret", jwt_secret="jwt-priority-secret")
    assert settings.secret_key == "jwt-priority-secret"


def test_frontend_admin_origin_parsing_from_comma_string() -> None:
    settings = _build_settings(
        frontend_admin_origin="http://localhost:5173,https://admin.guitaronline.dev",
    )
    assert settings.frontend_admin_origin == (
        "http://localhost:5173",
        "https://admin.guitaronline.dev",
    )


def test_debug_release_alias_is_parsed_as_false() -> None:
    settings = _build_settings(debug="release")
    assert settings.debug is False


def test_debug_development_alias_is_parsed_as_true() -> None:
    settings = _build_settings(debug="development")
    assert settings.debug is True


def test_kpi_excluded_email_prefixes_default_value() -> None:
    settings = _build_settings()
    assert settings.kpi_excluded_email_prefixes == ("synthetic-ops-",)


def test_kpi_excluded_email_prefixes_parsing_from_comma_string() -> None:
    settings = _build_settings(kpi_excluded_email_prefixes="synthetic-ops-,deploy-smoke-")
    assert settings.kpi_excluded_email_prefixes == ("synthetic-ops-", "deploy-smoke-")


def test_self_registration_is_enabled_by_default() -> None:
    settings = _build_settings()
    assert settings.auth_self_registration_enabled is True


def test_self_registration_flag_can_be_disabled() -> None:
    settings = _build_settings(auth_self_registration_enabled=False)
    assert settings.auth_self_registration_enabled is False
