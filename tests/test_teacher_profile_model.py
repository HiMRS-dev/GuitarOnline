from __future__ import annotations

from app.core.enums import TeacherStatusEnum
from app.modules.teachers.models import TeacherProfile, TeacherStatusType


def test_teacher_profile_status_enum_uses_lowercase_db_values() -> None:
    status_type = TeacherProfile.__table__.c.status.type

    assert isinstance(status_type, TeacherStatusType)
    assert status_type.impl.enums == [status.value for status in TeacherStatusEnum]


def test_teacher_profile_status_enum_tolerates_legacy_casing_on_read() -> None:
    status_type = TeacherProfile.__table__.c.status.type

    assert status_type.process_result_value("active", None) == TeacherStatusEnum.ACTIVE
    assert status_type.process_result_value("ACTIVE", None) == TeacherStatusEnum.ACTIVE
    assert status_type.process_result_value("disabled", None) == TeacherStatusEnum.DISABLED


def test_teacher_profile_status_enum_normalizes_bind_values() -> None:
    status_type = TeacherProfile.__table__.c.status.type

    assert status_type.process_bind_param(TeacherStatusEnum.ACTIVE, None) == "active"
    assert status_type.process_bind_param("ACTIVE", None) == "active"
