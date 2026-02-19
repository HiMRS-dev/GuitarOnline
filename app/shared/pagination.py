"""Reusable pagination helpers."""

from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination query params."""

    limit: int
    offset: int


def get_pagination_params(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginationParams:
    """FastAPI dependency for pagination params."""
    return PaginationParams(limit=limit, offset=offset)


class Page(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    total: int
    limit: int
    offset: int


def build_page(items: list[T], total: int, params: PaginationParams) -> Page[T]:
    """Build page object from query result and params."""
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)
