from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.enums import RoleEnum
from app.modules.lessons.service import LessonsService
from app.shared.exceptions import UnauthorizedException


@dataclass
class FakeLesson:
    id: UUID


class FakeLessonsRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def list_lessons_for_user(
        self,
        user_id: UUID,
        role_name: RoleEnum,
        limit: int,
        offset: int,
    ) -> tuple[list[FakeLesson], int]:
        self.calls.append(
            {
                "user_id": user_id,
                "role_name": role_name,
                "limit": limit,
                "offset": offset,
            },
        )
        return [FakeLesson(id=uuid4())], 1


def make_actor(role: RoleEnum, actor_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=actor_id or uuid4(), role=SimpleNamespace(name=role))


@pytest.mark.asyncio
async def test_list_lessons_allows_student_only() -> None:
    repository = FakeLessonsRepository()
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    student_id = uuid4()
    student = make_actor(RoleEnum.STUDENT, student_id)

    items, total = await service.list_lessons(student, limit=10, offset=0)

    assert total == 1
    assert len(items) == 1
    assert len(repository.calls) == 1
    assert repository.calls[0]["user_id"] == student_id
    assert repository.calls[0]["role_name"] == RoleEnum.STUDENT


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [RoleEnum.ADMIN, RoleEnum.TEACHER])
async def test_list_lessons_rejects_non_student_roles(role: RoleEnum) -> None:
    repository = FakeLessonsRepository()
    service = LessonsService(repository=repository)  # type: ignore[arg-type]
    actor = make_actor(role)

    with pytest.raises(UnauthorizedException, match="Only student can list own lessons"):
        await service.list_lessons(actor, limit=10, offset=0)

    assert repository.calls == []
