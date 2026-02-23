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


def test_custom_secret_key_allowed_in_production() -> None:
    settings = Settings(_env_file=None, app_env="production", secret_key="super-secure-value")
    assert settings.secret_key == "super-secure-value"
