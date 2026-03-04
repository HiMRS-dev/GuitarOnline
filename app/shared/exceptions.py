"""Custom exception hierarchy and handlers."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, details: dict | list | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundException(AppException):
    """Raised when entity is not found."""

    status_code = 404
    code = "not_found"


class ConflictException(AppException):
    """Raised when entity conflicts with current state."""

    status_code = 409
    code = "conflict"


class UnauthorizedException(AppException):
    """Raised when user has no rights for operation."""

    status_code = 403
    code = "forbidden"


class BusinessRuleException(AppException):
    """Raised when business rule validation fails."""

    status_code = 422
    code = "business_rule_violation"


class RateLimitException(AppException):
    """Raised when request rate exceeds configured limits."""

    status_code = 429
    code = "rate_limited"


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    """Handle custom domain exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions in unified shape."""
    status_code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
    }
    code = status_code_map.get(exc.status_code, "http_error")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": {"detail": exc.detail},
            },
        },
    )


def _normalize_validation_errors(errors: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in errors:
        normalized.append(
            {
                "loc": [str(part) for part in item.get("loc", ())],
                "message": item.get("msg"),
                "type": item.get("type"),
            },
        )
    return normalized


async def request_validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation exceptions in unified error shape."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": {"errors": _normalize_validation_errors(exc.errors())},
            },
        },
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Internal server error",
                "details": None,
            },
        },
    )


def register_exception_handlers(app) -> None:
    """Register global exception handlers."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
