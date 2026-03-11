from __future__ import annotations

from typing import Any, get_args, get_origin

from fastapi.routing import APIRoute
from pydantic import BaseModel

import app.main as main_module
from app.modules.admin.schemas import AdminTeacherDetailRead, AdminTeacherListItemRead
from app.modules.billing.schemas import PackageRead, PaymentRead
from app.modules.booking.schemas import BookingRead
from app.modules.lessons.schemas import LessonRead
from app.modules.teachers.schemas import TeacherProfileRead


def _collect_pydantic_models(annotation: Any) -> set[type[BaseModel]]:
    models: set[type[BaseModel]] = set()
    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            models.add(annotation)
        return models

    for arg in get_args(annotation):
        models.update(_collect_pydantic_models(arg))
    return models


def _model_contains_email(model: type[BaseModel], seen: set[type[BaseModel]]) -> bool:
    if model in seen:
        return False
    seen.add(model)

    if "email" in model.model_fields:
        return True

    for field in model.model_fields.values():
        nested_models = _collect_pydantic_models(field.annotation)
        for nested_model in nested_models:
            if _model_contains_email(nested_model, seen):
                return True
    return False


def _response_model_contains_email(annotation: Any) -> bool:
    for model in _collect_pydantic_models(annotation):
        if _model_contains_email(model, set()):
            return True
    return False


def test_non_admin_domain_models_do_not_expose_email_fields() -> None:
    for model in (
        TeacherProfileRead,
        BookingRead,
        LessonRead,
        PackageRead,
        PaymentRead,
    ):
        assert "email" not in model.model_fields


def test_admin_teacher_models_expose_email_for_admin_views() -> None:
    assert "email" in AdminTeacherListItemRead.model_fields
    assert "email" in AdminTeacherDetailRead.model_fields


def test_email_fields_are_exposed_only_on_identity_or_admin_routes() -> None:
    allowed_routes = {
        "/api/v1/identity/auth/register",
        "/api/v1/identity/users/me",
        "/api/v1/admin/teachers",
        "/api/v1/admin/teachers/{teacher_id}",
        "/api/v1/admin/teachers/{teacher_id}/verify",
        "/api/v1/admin/teachers/{teacher_id}/disable",
        "/api/v1/admin/users",
        "/api/v1/admin/users/provision",
        "/api/v1/admin/users/{user_id}/activate",
        "/api/v1/admin/users/{user_id}/deactivate",
    }

    for route in main_module.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.response_model is None:
            continue
        if not _response_model_contains_email(route.response_model):
            continue

        assert route.path in allowed_routes
