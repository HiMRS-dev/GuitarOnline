"""Custom exception hierarchy and handlers."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str) -> None:
        self.message = message
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


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    """Handle custom domain exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions in unified shape."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(exc.detail)}},
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Internal server error"}},
    )


def register_exception_handlers(app) -> None:
    """Register global exception handlers."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
