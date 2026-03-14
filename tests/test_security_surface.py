from __future__ import annotations

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

import app.main as main_module
from app.modules.admin.schemas import AdminUserListItemRead
from app.modules.identity.rate_limit import (
    enforce_login_rate_limit,
    enforce_refresh_rate_limit,
    enforce_register_rate_limit,
)
from app.modules.identity.schemas import TokenPair, UserCreate, UserRead


def _route(path: str, method: str) -> APIRoute:
    for route in main_module.app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route {method} {path} was not found")


def test_cors_middleware_uses_frontend_admin_origin_setting() -> None:
    cors_middleware = next(
        (item for item in main_module.app.user_middleware if item.cls is CORSMiddleware),
        None,
    )
    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == list(
        main_module.settings.frontend_admin_origin,
    )
    assert cors_middleware.kwargs["allow_credentials"] is True
    assert cors_middleware.kwargs["allow_methods"] == ["*"]
    assert cors_middleware.kwargs["allow_headers"] == ["*"]


def test_identity_auth_routes_keep_rate_limit_dependencies() -> None:
    register_route = _route("/api/v1/identity/auth/register", "POST")
    login_route = _route("/api/v1/identity/auth/login", "POST")
    refresh_route = _route("/api/v1/identity/auth/refresh", "POST")

    register_dependencies = {
        dependency.call for dependency in register_route.dependant.dependencies
    }
    login_dependencies = {dependency.call for dependency in login_route.dependant.dependencies}
    refresh_dependencies = {dependency.call for dependency in refresh_route.dependant.dependencies}

    assert enforce_register_rate_limit in register_dependencies
    assert enforce_login_rate_limit in login_dependencies
    assert enforce_refresh_rate_limit in refresh_dependencies


def test_identity_response_models_are_minimized() -> None:
    register_route = _route("/api/v1/identity/auth/register", "POST")
    login_route = _route("/api/v1/identity/auth/login", "POST")
    me_route = _route("/api/v1/identity/users/me", "GET")

    assert register_route.response_model is UserRead
    assert login_route.response_model is TokenPair
    assert me_route.response_model is UserRead

    forbidden_fields = {"password", "password_hash", "role_id", "secret_key"}
    for field_name in forbidden_fields:
        assert field_name not in UserRead.model_fields
        assert field_name not in TokenPair.model_fields


def test_public_registration_request_schema_does_not_expose_role() -> None:
    assert "role" not in UserCreate.model_fields


def test_admin_role_change_response_model_is_minimized() -> None:
    role_route = _route("/api/v1/admin/users/{user_id}/role", "POST")
    assert role_route.response_model is AdminUserListItemRead

    forbidden_fields = {"password", "password_hash", "role_id", "secret_key"}
    for field_name in forbidden_fields:
        assert field_name not in AdminUserListItemRead.model_fields


def test_legacy_admin_provision_route_is_removed() -> None:
    with pytest.raises(AssertionError):
        _route("/api/v1/admin/users/provision", "POST")


def test_legacy_admin_teacher_verify_route_is_removed() -> None:
    with pytest.raises(AssertionError):
        _route("/api/v1/admin/teachers/{teacher_id}/verify", "POST")
