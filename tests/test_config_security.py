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
