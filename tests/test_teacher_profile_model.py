from __future__ import annotations

from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect

from app.core.enums import TeacherStatusEnum
from app.modules.teachers.models import TeacherProfile, TeacherStatusType


def test_teacher_profile_status_enum_uses_lowercase_db_values() -> None:
    status_type = TeacherProfile.__table__.c.status.type

    assert isinstance(status_type, TeacherStatusType)
    assert status_type.impl.length == 16


def test_teacher_profile_status_enum_tolerates_legacy_casing_on_read() -> None:
    status_type = TeacherProfile.__table__.c.status.type
    processor = status_type.result_processor(postgresql_dialect(), None)

    assert processor is not None
    assert processor("active") == TeacherStatusEnum.ACTIVE
    assert processor("ACTIVE") == TeacherStatusEnum.ACTIVE
    assert processor("disabled") == TeacherStatusEnum.DISABLED
    assert processor("DISABLED") == TeacherStatusEnum.DISABLED


def test_teacher_profile_status_enum_normalizes_bind_values() -> None:
    status_type = TeacherProfile.__table__.c.status.type
    processor = status_type.bind_processor(postgresql_dialect())

    assert processor is not None
    assert processor(TeacherStatusEnum.ACTIVE) == "active"
    assert processor("ACTIVE") == "active"
