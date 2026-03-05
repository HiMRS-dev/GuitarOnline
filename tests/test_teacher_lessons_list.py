from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum
from app.modules.lessons.service import LessonsService
from app.shared.exceptions import BusinessRuleException, UnauthorizedException


@dataclass
class FakeLesson:
    id: UUID


class FakeLessonsRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def list_teacher_lessons(
        self,
        *,
        teacher_id: UUID,
        from_utc,
        to_utc,
        limit: int,
        offset: int,
    ) -> tuple[list[FakeLesson], int]:
        self.calls.append(
            {
                "teacher_id": teacher_id,
                "from_utc": from_utc,
                "to_utc": to_utc,
                "limit": limit,
                "offset": offset,
            },
        )
        return [FakeLesson(id=uuid4())], 1


def make_actor(role: RoleEnum, actor_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=actor_id or uuid4(), role=SimpleNamespace(name=role))


@pytest.mark.asyncio
async def test_list_teacher_lessons_passes_filters_and_teacher_scope() -> None:
    repository = FakeLessonsRepository()
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher_id = uuid4()
    teacher = make_actor(RoleEnum.TEACHER, teacher_id)
    from_utc = datetime(2026, 3, 7, 10, 0, tzinfo=UTC)
    to_utc = datetime(2026, 3, 9, 10, 0, tzinfo=UTC)

    items, total = await service.list_teacher_lessons(
        teacher,
        from_utc=from_utc,
        to_utc=to_utc,
        limit=20,
        offset=5,
    )

    assert total == 1
    assert len(items) == 1
    assert len(repository.calls) == 1
    assert repository.calls[0]["teacher_id"] == teacher_id
    assert repository.calls[0]["from_utc"] == from_utc
    assert repository.calls[0]["to_utc"] == to_utc
    assert repository.calls[0]["limit"] == 20
    assert repository.calls[0]["offset"] == 5


@pytest.mark.asyncio
async def test_list_teacher_lessons_requires_teacher_role() -> None:
    repository = FakeLessonsRepository()
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    student = make_actor(RoleEnum.STUDENT)

    with pytest.raises(UnauthorizedException, match="Only teacher can list teacher lessons"):
        await service.list_teacher_lessons(
            student,
            from_utc=None,
            to_utc=None,
            limit=10,
            offset=0,
        )

    assert repository.calls == []


@pytest.mark.asyncio
async def test_list_teacher_lessons_rejects_invalid_range() -> None:
    repository = FakeLessonsRepository()
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    teacher = make_actor(RoleEnum.TEACHER)

    with pytest.raises(
        BusinessRuleException,
        match="from_utc must be less than or equal to to_utc",
    ):
        await service.list_teacher_lessons(
            teacher,
            from_utc=datetime(2026, 3, 10, 0, 0, tzinfo=UTC),
            to_utc=datetime(2026, 3, 9, 0, 0, tzinfo=UTC),
            limit=10,
            offset=0,
        )

    assert repository.calls == []
