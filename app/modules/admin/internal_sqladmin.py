"""Internal SQLAdmin surface for operational support/debug workflows."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, Request
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.core.enums import RoleEnum
from app.core.security import verify_password
from app.modules.billing.models import LessonPackage
from app.modules.booking.models import Booking
from app.modules.identity.models import Role, User
from app.modules.scheduling.models import AvailabilitySlot
from app.modules.teachers.models import TeacherProfile

_SESSION_USER_ID_KEY = "internal_admin_user_id"


class InternalAdminAuthBackend(AuthenticationBackend):
    """Authenticate SQLAdmin users against platform admins only."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", "")).strip().lower()
        password = str(form.get("password", ""))
        if not email or not password:
            return False

        async with SessionLocal() as session:
            stmt = (
                select(
                    User.id,
                    User.email,
                    User.password_hash,
                    User.is_active,
                    Role.name.label("role_name"),
                )
                .join(Role, User.role_id == Role.id)
                .where(User.email == email)
                .limit(1)
            )
            row = (await session.execute(stmt)).mappings().first()

        if row is None:
            return False
        if not row["is_active"]:
            return False
        if row["role_name"] != RoleEnum.ADMIN:
            return False
        if not verify_password(password, row["password_hash"]):
            return False

        request.session[_SESSION_USER_ID_KEY] = str(row["id"])
        return True

    async def logout(self, request: Request) -> bool:
        request.session.pop(_SESSION_USER_ID_KEY, None)
        return True

    async def authenticate(self, request: Request) -> bool:
        raw_user_id = request.session.get(_SESSION_USER_ID_KEY)
        if raw_user_id is None:
            return False

        try:
            user_id = UUID(str(raw_user_id))
        except ValueError:
            return False

        async with SessionLocal() as session:
            stmt = (
                select(User.id)
                .join(Role, User.role_id == Role.id)
                .where(
                    User.id == user_id,
                    User.is_active.is_(True),
                    Role.name == RoleEnum.ADMIN,
                )
                .limit(1)
            )
            existing_user_id = await session.scalar(stmt)

        return existing_user_id is not None


class _ReadOnlyView(ModelView):
    """Conservative read-only defaults for internal operational console."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    page_size = 50
    page_size_options = [25, 50, 100]


class UserAdminView(_ReadOnlyView, model=User):
    """Read-only users view with role context."""

    category = "Identity"
    name = "User"
    name_plural = "Users"
    column_list = [
        User.id,
        User.email,
        User.full_name,
        User.role_id,
        User.timezone,
        User.is_active,
        User.created_at,
        User.updated_at,
    ]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.created_at, User.updated_at, User.email]


class TeacherProfileAdminView(_ReadOnlyView, model=TeacherProfile):
    """Read-only teacher profile view."""

    category = "Teachers"
    name = "Teacher profile"
    name_plural = "Teacher profiles"
    column_list = [
        TeacherProfile.id,
        TeacherProfile.user_id,
        TeacherProfile.display_name,
        TeacherProfile.status,
        TeacherProfile.experience_years,
        TeacherProfile.created_at,
        TeacherProfile.updated_at,
    ]
    column_searchable_list = [TeacherProfile.display_name]
    column_sortable_list = [TeacherProfile.created_at, TeacherProfile.updated_at]


class SlotAdminView(_ReadOnlyView, model=AvailabilitySlot):
    """Read-only slot view for scheduling diagnostics."""

    category = "Scheduling"
    name = "Slot"
    name_plural = "Slots"
    column_list = [
        AvailabilitySlot.id,
        AvailabilitySlot.teacher_id,
        AvailabilitySlot.created_by_admin_id,
        AvailabilitySlot.start_at,
        AvailabilitySlot.end_at,
        AvailabilitySlot.status,
        AvailabilitySlot.blocked_at,
        AvailabilitySlot.created_at,
    ]
    column_sortable_list = [AvailabilitySlot.start_at, AvailabilitySlot.created_at]
    column_default_sort = [("start_at", False)]


class BookingAdminView(_ReadOnlyView, model=Booking):
    """Read-only booking view for chain diagnostics."""

    category = "Booking"
    name = "Booking"
    name_plural = "Bookings"
    column_list = [
        Booking.id,
        Booking.slot_id,
        Booking.student_id,
        Booking.teacher_id,
        Booking.package_id,
        Booking.status,
        Booking.hold_expires_at,
        Booking.confirmed_at,
        Booking.canceled_at,
        Booking.created_at,
    ]
    column_sortable_list = [Booking.created_at, Booking.updated_at]
    column_default_sort = [("created_at", True)]


class PackageAdminView(_ReadOnlyView, model=LessonPackage):
    """Read-only package view for billing diagnostics."""

    category = "Billing"
    name = "Package"
    name_plural = "Packages"
    column_list = [
        LessonPackage.id,
        LessonPackage.student_id,
        LessonPackage.lessons_total,
        LessonPackage.lessons_left,
        LessonPackage.lessons_reserved,
        LessonPackage.status,
        LessonPackage.expires_at,
        LessonPackage.created_at,
    ]
    column_sortable_list = [LessonPackage.created_at, LessonPackage.expires_at]
    column_default_sort = [("created_at", True)]


def configure_internal_sqladmin(app: FastAPI, secret_key: str) -> Admin:
    """Attach SQLAdmin app under /internal-admin with strict admin auth."""

    auth_backend = InternalAdminAuthBackend(secret_key=secret_key)
    internal_admin = Admin(
        app=app,
        engine=engine,
        title="GuitarOnline Internal Admin",
        base_url="/internal-admin",
        authentication_backend=auth_backend,
    )
    internal_admin.add_view(UserAdminView)
    internal_admin.add_view(TeacherProfileAdminView)
    internal_admin.add_view(SlotAdminView)
    internal_admin.add_view(BookingAdminView)
    internal_admin.add_view(PackageAdminView)
    return internal_admin
