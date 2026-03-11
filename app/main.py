"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal, close_engine
from app.core.metrics import build_metrics_response, instrument_http_request
from app.modules.admin.router import router as admin_router
from app.modules.audit.router import router as audit_router
from app.modules.billing.router import router as billing_router
from app.modules.booking.router import router as booking_router
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.router import router as identity_router
from app.modules.identity.service import IdentityService
from app.modules.lessons.me_router import router as me_lessons_router
from app.modules.lessons.router import router as lessons_router
from app.modules.lessons.teacher_router import router as teacher_lessons_router
from app.modules.notifications.router import router as notifications_router
from app.modules.scheduling.router import router as scheduling_router
from app.modules.teachers.router import router as teachers_router
from app.shared.exceptions import register_exception_handlers
from app.shared.utils import utc_now

settings = get_settings()
logger = logging.getLogger(__name__)
_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
_FRONTEND_STATIC_DIR = _FRONTEND_DIR / "static"
_PUBLIC_HOME_PAGE = Path(__file__).resolve().parent.parent / "index.html"
_OPENAPI_TAGS = [
    {"name": "identity", "description": "Authentication and current-user identity endpoints."},
    {"name": "teachers", "description": "Teacher profile management endpoints."},
    {"name": "scheduling", "description": "Teacher availability slot endpoints."},
    {"name": "booking", "description": "Booking hold/confirm/cancel/reschedule endpoints."},
    {"name": "billing", "description": "Lesson package and payment endpoints."},
    {"name": "lessons", "description": "Lesson lifecycle endpoints."},
    {"name": "notifications", "description": "Notification delivery endpoints."},
    {"name": "admin", "description": "Admin-only KPI and operational endpoints."},
    {"name": "audit", "description": "Audit log and outbox administration endpoints."},
]
_OPENAPI_TAG_NAME_RU: dict[str, str] = {
    "identity": "Идентификация",
    "teachers": "Преподаватели",
    "scheduling": "Расписание",
    "booking": "Бронирования",
    "billing": "Платежи и пакеты",
    "lessons": "Уроки",
    "notifications": "Уведомления",
    "admin": "Администрирование",
    "audit": "Аудит",
}
_OPENAPI_SUMMARY_RU: dict[str, str] = {
    "Block Admin Slot": "Заблокировать слот (админ)",
    "Bulk Create Admin Slots": "Массово создать слоты (админ)",
    "Cancel Admin Booking": "Отменить бронирование (админ)",
    "Cancel Booking": "Отменить бронирование",
    "Complete Lesson": "Завершить урок",
    "Confirm Booking": "Подтвердить бронирование",
    "Create Admin Action": "Создать действие администратора",
    "Create Admin Package": "Создать пакет (админ)",
    "Create Admin Slot": "Создать слот (админ)",
    "Create Lesson": "Создать урок",
    "Create Log": "Создать запись аудита",
    "Create Notification": "Создать уведомление",
    "Create Package": "Создать пакет",
    "Create Payment": "Создать платеж",
    "Create Profile": "Создать профиль",
    "Create Slot": "Создать слот",
    "Delete Admin Slot": "Удалить слот (админ)",
    "Disable Admin Teacher": "Отключить преподавателя (админ)",
    "Expire Booking Holds": "Завершить просроченные HOLD-бронирования",
    "Expire Packages": "Завершить просроченные пакеты",
    "Get Admin Kpi Overview": "Получить обзор KPI (админ)",
    "Get Admin Kpi Sales": "Получить KPI продаж (админ)",
    "Get Admin Operations Overview": "Получить операционный обзор (админ)",
    "Get Admin Slot Stats": "Получить статистику слотов (админ)",
    "Get Admin Teacher Detail": "Получить карточку преподавателя (админ)",
    "Get Delivery Metrics": "Получить метрики доставки",
    "Get Me": "Получить мой профиль",
    "Healthcheck": "Проверка работоспособности",
    "Hold Booking": "Создать HOLD-бронирование",
    "List Admin Actions": "Список действий администратора",
    "List Admin Bookings": "Список бронирований (админ)",
    "List Admin Notifications": "Список уведомлений (админ)",
    "List Admin Packages": "Список пакетов (админ)",
    "List Admin Slots": "Список слотов (админ)",
    "List Admin Teachers": "Список преподавателей (админ)",
    "List Logs": "Список логов",
    "List My Bookings": "Мои бронирования",
    "List My Lessons": "Мои уроки",
    "List My Lessons Alias": "Мои уроки (алиас)",
    "List My Notifications": "Мои уведомления",
    "List Open Slots": "Список открытых слотов",
    "List Pending Outbox": "Список pending outbox-событий",
    "List Profiles": "Список профилей",
    "List Student Packages": "Список пакетов студента",
    "List Teacher Lessons": "Список уроков преподавателя",
    "Login": "Вход",
    "Logout": "Выход",
    "Mark Admin Lesson No Show": "Отметить неявку на урок (админ)",
    "Provision Admin User": "Создать пользователя (админ)",
    "Readiness Check": "Проверка готовности",
    "Refresh Tokens": "Обновить токены",
    "Register": "Регистрация",
    "Report Teacher Lesson": "Сохранить отчет преподавателя по уроку",
    "Reschedule Admin Booking": "Перенести бронирование (админ)",
    "Reschedule Booking": "Перенести бронирование",
    "Update Lesson": "Обновить урок",
    "Update Notification Status": "Обновить статус уведомления",
    "Update Payment Status": "Обновить статус платежа",
    "Update Profile": "Обновить профиль",
    "Verify Admin Teacher": "Верифицировать преподавателя (админ)",
}
_OPENAPI_DESCRIPTION_RU: dict[str, str] = {
    "Authentication and current-user identity endpoints.": (
        "Эндпоинты аутентификации и данных текущего пользователя."
    ),
    "Teacher profile management endpoints.": "Эндпоинты управления профилями преподавателей.",
    "Teacher availability slot endpoints.": "Эндпоинты слотов доступности преподавателей.",
    "Booking hold/confirm/cancel/reschedule endpoints.": (
        "Эндпоинты HOLD/подтверждения/отмены/переноса бронирований."
    ),
    "Lesson package and payment endpoints.": "Эндпоинты пакетов уроков и платежей.",
    "Lesson lifecycle endpoints.": "Эндпоинты жизненного цикла уроков.",
    "Notification delivery endpoints.": "Эндпоинты доставки уведомлений.",
    "Admin-only KPI and operational endpoints.": (
        "Админ-эндпоинты KPI и операционного контроля."
    ),
    "Audit log and outbox administration endpoints.": (
        "Эндпоинты журнала аудита и администрирования outbox."
    ),
    "Alias for /lessons/my contract stability.": (
        "Алиас для /lessons/my для стабильности контракта."
    ),
    "Block slot and persist reason with audit trace.": (
        "Блокирует слот и сохраняет причину с аудит-следом."
    ),
    "Bulk create slots from admin schedule template.": (
        "Массово создает слоты по админ-шаблону расписания."
    ),
    "Cancel booking and apply refund policy.": (
        "Отменяет бронирование и применяет политику возврата."
    ),
    "Cancel booking via admin-only flow with explicit reason.": (
        "Отменяет бронирование через админ-процесс с обязательной причиной."
    ),
    "Confirm booking from HOLD to CONFIRMED.": (
        "Подтверждает бронирование из HOLD в CONFIRMED."
    ),
    "Create a lesson package (admin only).": "Создает пакет уроков (только admin).",
    "Create admin action log.": "Создает запись журнала админ-действий.",
    "Create audit log entry.": "Создает запись аудита.",
    "Create availability slot with strict admin validation.": (
        "Создает слот доступности с жесткой админ-валидацией."
    ),
    "Create availability slot.": "Создает слот доступности.",
    "Create booking in HOLD state.": "Создает бронирование в статусе HOLD.",
    "Create lesson.": "Создает урок.",
    "Create manual package with price snapshot under admin contract.": (
        "Создает пакет вручную со снимком цены в рамках админ-контракта."
    ),
    "Create notification.": "Создает уведомление.",
    "Create payment record.": "Создает запись платежа.",
    "Create teacher profile.": "Создает профиль преподавателя.",
    "Delete slot when no related bookings exist.": (
        "Удаляет слот, если нет связанных бронирований."
    ),
    "Disable teacher profile from admin panel.": (
        "Отключает профиль преподавателя из админ-панели."
    ),
    "Expire outdated active lesson packages (admin).": (
        "Завершает просроченные активные пакеты уроков (admin)."
    ),
    "Expire stale holds (admin task endpoint).": (
        "Завершает просроченные HOLD (админ-эндпоинт задачи)."
    ),
    "Get admin KPI overview snapshot.": "Возвращает снимок общего KPI для админа.",
    "Get admin sales KPI snapshot for requested UTC interval.": (
        "Возвращает снимок KPI продаж админа за заданный UTC-интервал."
    ),
    "Get operational overview snapshot.": "Возвращает снимок операционного состояния.",
    "Get teacher detail for admin views.": (
        "Возвращает детальную карточку преподавателя для админ-интерфейса."
    ),
    "List admin action logs.": "Возвращает журнал админ-действий.",
    "List audit logs.": "Возвращает журнал аудита.",
    "List bookings for admin operations with filters.": (
        "Возвращает бронирования для админ-операций с фильтрами."
    ),
    "List bookings for current user.": "Возвращает бронирования текущего пользователя.",
    "List currently open slots.": "Возвращает текущие открытые слоты.",
    "List lesson packages for admin billing operations with filters.": (
        "Возвращает пакеты уроков для админ-биллинга с фильтрами."
    ),
    "List lessons for current student.": "Возвращает уроки текущего студента.",
    "List notification delivery journal with admin filters.": (
        "Возвращает журнал доставки уведомлений с админ-фильтрами."
    ),
    "List notifications for current user.": "Возвращает уведомления текущего пользователя.",
    "List packages for a specific student.": "Возвращает пакеты конкретного студента.",
    "List pending outbox events.": "Возвращает pending-события outbox.",
    "List slots for admin calendar views with aggregated booking status.": (
        "Возвращает слоты для админ-календаря с агрегированным статусом бронирования."
    ),
    "List teacher profiles.": "Возвращает профили преподавателей.",
    "List teacher-owned lessons with optional UTC range filters.": (
        "Возвращает уроки преподавателя с опциональными UTC-фильтрами диапазона."
    ),
    "List teachers for admin filters by status/verification/query/tag.": (
        "Возвращает преподавателей для админа с фильтрами по статусу, верификации, поиску и тегам."
    ),
    "Liveness probe endpoint.": "Эндпоинт проверки живости сервиса.",
    "Mark lesson as completed and consume reserved package lesson.": (
        "Отмечает урок завершенным и списывает зарезервированный урок из пакета."
    ),
    "Mark lesson as NO_SHOW via admin-only operation.": (
        "Отмечает урок как NO_SHOW через админ-операцию."
    ),
    "Provision teacher/admin accounts through protected admin workflow.": (
        "Создает аккаунты teacher/admin через защищенный админ-процесс."
    ),
    "Readiness probe endpoint with DB dependency check.": (
        "Эндпоинт проверки готовности с проверкой БД."
    ),
    "Register a new account.": "Регистрирует новый аккаунт.",
    "Reschedule booking using cancel + new booking flow.": (
        "Переносит бронирование через сценарий отмены и создания нового бронирования."
    ),
    "Reschedule booking via admin-only atomic flow.": (
        "Переносит бронирование через атомарный админ-сценарий."
    ),
    "Return admin slot stats with final bucket semantics.": (
        "Возвращает статистику админ-слотов с финальной bucket-семантикой."
    ),
    "Return delivery observability metrics.": "Возвращает метрики наблюдаемости доставки.",
    "Return profile of authenticated user.": (
        "Возвращает профиль аутентифицированного пользователя."
    ),
    "Revoke refresh token when present and clear refresh cookie.": (
        "Отзывает refresh-токен (если есть) и очищает refresh-cookie."
    ),
    "Rotate refresh token and issue new token pair.": (
        "Ротирует refresh-токен и выдает новую пару токенов."
    ),
    "Save teacher report payload for own lesson.": (
        "Сохраняет отчет преподавателя по своему уроку."
    ),
    "Sign in by email/password and return JWT token pair.": (
        "Выполняет вход по email/паролю и возвращает пару JWT-токенов."
    ),
    "Successful Response": "Успешный ответ",
    "Update lesson.": "Обновляет урок.",
    "Update notification status.": "Обновляет статус уведомления.",
    "Update payment status (admin).": "Обновляет статус платежа (admin).",
    "Update teacher profile.": "Обновляет профиль преподавателя.",
    "Validation Error": "Ошибка валидации",
    "Verify teacher profile from admin panel.": (
        "Верифицирует профиль преподавателя из админ-панели."
    ),
    "Access + refresh JWT response.": "Ответ с access и refresh JWT.",
    "Admin action response schema.": "Схема ответа админ-действия.",
    "Admin booking list item with slot scheduling context.": (
        "Элемент списка админ-бронирований с контекстом расписания слота."
    ),
    "Admin KPI snapshot across core domains.": "Снимок KPI админа по ключевым доменам.",
    "Admin notifications log item with delivery metadata.": (
        "Элемент журнала админ-уведомлений с метаданными доставки."
    ),
    "Admin package list item with lifecycle state and student linkage.": (
        "Элемент списка админ-пакетов с состоянием жизненного цикла и привязкой к студенту."
    ),
    "Admin request schema for booking cancellation.": (
        "Схема админ-запроса на отмену бронирования."
    ),
    "Admin request schema for booking reschedule.": (
        "Схема админ-запроса на перенос бронирования."
    ),
    "Admin request schema for bulk slot generation.": (
        "Схема админ-запроса на массовую генерацию слотов."
    ),
    "Admin request schema for manual package creation with price snapshot.": (
        "Схема админ-запроса на ручное создание пакета со снимком цены."
    ),
    "Admin request schema for single slot creation.": (
        "Схема админ-запроса на создание одного слота."
    ),
    "Admin request schema for slot blocking.": "Схема админ-запроса на блокировку слота.",
    "Admin response schema for blocked slot state.": (
        "Схема админ-ответа для состояния заблокированного слота."
    ),
    "Admin response schema for created package with price snapshot.": (
        "Схема админ-ответа для созданного пакета со снимком цены."
    ),
    "Admin response schema for created slot.": "Схема админ-ответа для созданного слота.",
    "Admin sales KPI snapshot for requested UTC range.": (
        "Снимок KPI продаж админа за запрошенный UTC-диапазон."
    ),
    "Admin slot list item with aggregated booking status.": (
        "Элемент списка админ-слотов с агрегированным статусом бронирования."
    ),
    "Admin slot stats with final-bucket semantics.": (
        "Статистика админ-слотов с финальной bucket-семантикой."
    ),
    "Admin teacher detail with profile metadata and moderation fields.": (
        "Детальная карточка преподавателя для админа с метаданными профиля и полями модерации."
    ),
    "Admin teacher list item with search/filter metadata.": (
        "Элемент списка преподавателей для админа с метаданными поиска и фильтрации."
    ),
    "Admin-only user provisioning request for elevated roles.": (
        "Админ-схема запроса на создание пользователя с повышенными ролями."
    ),
    "Aggregated booking state for admin slot views.": (
        "Агрегированное состояние бронирования для админ-представлений слотов."
    ),
    "Audit log response schema.": "Схема ответа журнала аудита.",
    "Availability slot response schema.": "Схема ответа слота доступности.",
    "Availability slot status.": "Статус слота доступности.",
    "Booking lifecycle status.": "Статус жизненного цикла бронирования.",
    "Booking response schema.": "Схема ответа бронирования.",
    "Bulk slot creation response summary.": "Сводка ответа массового создания слотов.",
    "Cancel booking request.": "Запрос на отмену бронирования.",
    "Create admin action request.": "Запрос на создание админ-действия.",
    "Create audit log request.": "Запрос на создание записи аудита.",
    "Create availability slot request.": "Запрос на создание слота доступности.",
    "Create booking hold request.": "Запрос на создание HOLD-бронирования.",
    "Create lesson package request.": "Запрос на создание пакета уроков.",
    "Create lesson request.": "Запрос на создание урока.",
    "Create notification request.": "Запрос на создание уведомления.",
    "Create payment request.": "Запрос на создание платежа.",
    "Create teacher profile request.": "Запрос на создание профиля преподавателя.",
    "Credentials for login.": "Учетные данные для входа.",
    "Delivery observability snapshot for notifications pipeline.": (
        "Снимок наблюдаемости доставки для пайплайна уведомлений."
    ),
    "Excluded time interval for bulk slot generation.": (
        "Исключаемый временной интервал для массовой генерации слотов."
    ),
    "Lesson package response schema.": "Схема ответа пакета уроков.",
    "Lesson package status.": "Статус пакета уроков.",
    "Lesson response schema.": "Схема ответа урока.",
    "Lesson status.": "Статус урока.",
    "Notification delivery status.": "Статус доставки уведомления.",
    "Notification response schema.": "Схема ответа уведомления.",
    "Operational snapshot for admin runbook checks.": (
        "Операционный снимок для проверок админ-ранбука."
    ),
    "Outbox event response schema.": "Схема ответа outbox-события.",
    "Outbox event status for integration publishing.": (
        "Статус outbox-события для интеграционной публикации."
    ),
    "Payment processing status.": "Статус обработки платежа.",
    "Payment response schema.": "Схема ответа платежа.",
    "Provisioned teacher profile snapshot in admin response.": (
        "Снимок созданного профиля преподавателя в админ-ответе."
    ),
    "Provisioned user response without sensitive fields.": (
        "Ответ по созданному пользователю без чувствительных полей."
    ),
    "Refresh token payload.": "Данные refresh-токена.",
    "Reschedule booking request.": "Запрос на перенос бронирования.",
    "Role response schema.": "Схема ответа роли.",
    "Skipped candidate slot in bulk create response.": (
        "Пропущенный кандидат в слоты в ответе массового создания."
    ),
    "System roles.": "Системные роли.",
    "Teacher profile moderation status.": "Статус модерации профиля преподавателя.",
    "Teacher profile payload for admin provisioning flow.": (
        "Данные профиля преподавателя для админ-процесса создания пользователя."
    ),
    "Teacher profile response schema.": "Схема ответа профиля преподавателя.",
    "Teacher report payload for lesson outcomes and materials.": (
        "Данные отчета преподавателя по результатам урока и материалам."
    ),
    "Update lesson request.": "Запрос на обновление урока.",
    "Update notification status request.": "Запрос на обновление статуса уведомления.",
    "Update payment status request.": "Запрос на обновление статуса платежа.",
    "Update teacher profile request.": "Запрос на обновление профиля преподавателя.",
    "User output schema.": "Схема ответа пользователя.",
    "User registration request.": "Запрос на регистрацию пользователя.",
}


def _translate_openapi_texts(node: Any) -> None:
    """Translate OpenAPI human-facing text fields to Russian."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                if key == "summary":
                    node[key] = _OPENAPI_SUMMARY_RU.get(value, value)
                elif key == "description":
                    node[key] = _OPENAPI_DESCRIPTION_RU.get(value, value)
            else:
                _translate_openapi_texts(value)
        return

    if isinstance(node, list):
        for item in node:
            _translate_openapi_texts(item)


def _localize_openapi_schema(schema: dict[str, Any]) -> None:
    """Apply Russian localization for OpenAPI schema visible in Swagger UI."""
    info = schema.setdefault("info", {})
    info["title"] = f"{settings.app_name} API"
    info["description"] = "Документация API проекта GuitarOnline на русском языке."

    tags = schema.get("tags", [])
    tag_name_mapping: dict[str, str] = {}
    if isinstance(tags, list):
        for item in tags:
            if not isinstance(item, dict):
                continue
            source_name = item.get("name")
            if not isinstance(source_name, str):
                continue
            target_name = _OPENAPI_TAG_NAME_RU.get(source_name)
            if target_name:
                item["name"] = target_name
                tag_name_mapping[source_name] = target_name

    paths = schema.get("paths", {})
    if isinstance(paths, dict):
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                op_tags = operation.get("tags")
                if not isinstance(op_tags, list):
                    continue
                operation["tags"] = [
                    tag_name_mapping.get(tag, tag) if isinstance(tag, str) else tag
                    for tag in op_tags
                ]

    _translate_openapi_texts(schema)


def _build_csp_header(path: str) -> str | None:
    """Return CSP policy for selected routes."""
    if path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi"):
        return None
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )


def _landing_page_html() -> str:
    """Build minimal landing page for root path."""
    return f"""
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{settings.app_name} API</title>
    <style>
      :root {{
        color-scheme: light;
      }}
      body {{
        margin: 0;
        font-family: "Segoe UI", Arial, sans-serif;
        background: linear-gradient(135deg, #f3f8ff 0%, #eef4f0 100%);
        color: #1c2a34;
      }}
      .container {{
        max-width: 860px;
        margin: 48px auto;
        padding: 0 20px;
      }}
      .hero {{
        background: #ffffff;
        border-radius: 16px;
        border: 1px solid #dce7ea;
        box-shadow: 0 10px 28px rgba(20, 31, 46, 0.08);
        padding: 28px;
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 2rem;
      }}
      p {{
        margin: 0;
        line-height: 1.5;
      }}
      .links {{
        margin-top: 22px;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 10px;
      }}
      a {{
        display: block;
        text-decoration: none;
        border-radius: 10px;
        border: 1px solid #c6d7db;
        background: #f9fcff;
        color: #16384a;
        padding: 10px 12px;
      }}
      a:hover {{
        border-color: #93b2ba;
        background: #f0f8ff;
      }}
      code {{
        display: inline-block;
        margin-top: 10px;
        font-size: 0.9rem;
        background: #f0f4f6;
        border-radius: 6px;
        padding: 4px 6px;
      }}
    </style>
  </head>
  <body>
    <main class="container">
      <section class="hero">
        <h1>{settings.app_name} API</h1>
        <p>Сервис backend запущен. Используйте ссылки ниже для доступа к документации и пробам.</p>
        <div class="links">
          <a href="/home">Главная страница</a>
          <a href="/portal">Личный кабинет MVP</a>
          <a href="/docs">Документация API</a>
          <a href="/health">Проверка Health</a>
          <a href="/ready">Проверка Ready</a>
          <a href="/metrics">Метрики</a>
        </div>
        <code>Базовый префикс API: {settings.api_prefix}</code>
      </section>
    </main>
  </body>
</html>
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup and shutdown hooks."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting %s", settings.app_name)

    async with SessionLocal() as session:
        try:
            service = IdentityService(IdentityRepository(session))
            await service.ensure_default_roles()
            await session.commit()
            logger.info("Default roles ensured")
        except Exception:
            await session.rollback()
            logger.exception("Failed during startup initialization")
            raise

    yield

    logger.info("Shutting down %s", settings.app_name)
    await close_engine()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
    openapi_tags=_OPENAPI_TAGS,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_admin_origin),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(instrument_http_request)


@app.middleware("http")
async def apply_security_headers(request: Request, call_next):
    """Attach baseline security headers to HTTP responses."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    csp_header = _build_csp_header(request.url.path)
    if csp_header:
        response.headers.setdefault("Content-Security-Policy", csp_header)
    return response


app.mount("/portal/static", StaticFiles(directory=_FRONTEND_STATIC_DIR), name="portal-static")

register_exception_handlers(app)

app.include_router(identity_router, prefix=settings.api_prefix)
app.include_router(teachers_router, prefix=settings.api_prefix)
app.include_router(scheduling_router, prefix=settings.api_prefix)
app.include_router(booking_router, prefix=settings.api_prefix)
app.include_router(billing_router, prefix=settings.api_prefix)
app.include_router(lessons_router, prefix=settings.api_prefix)
app.include_router(teacher_lessons_router, prefix=settings.api_prefix)
app.include_router(me_lessons_router, prefix=settings.api_prefix)
app.include_router(notifications_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(audit_router, prefix=settings.api_prefix)


def custom_openapi() -> dict[str, Any]:
    """Build and cache localized OpenAPI schema for Swagger/ReDoc."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=settings.app_name,
        version=app.version,
        routes=app.routes,
        tags=_OPENAPI_TAGS,
    )
    _localize_openapi_schema(schema)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/docs", include_in_schema=False)
async def swagger_docs() -> HTMLResponse:
    """Serve Swagger UI with Russian page title."""
    base_response = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{settings.app_name} - Документация API",
        oauth2_redirect_url="/docs/oauth2-redirect",
    )
    content = base_response.body.decode("utf-8")
    localization_script = """
<script>
(() => {
  const textMap = {
    "Authorize": "Авторизация",
    "Available authorizations": "Доступные способы авторизации",
    "Try it out": "Попробовать",
    "Execute": "Выполнить",
    "Cancel": "Отмена",
    "Responses": "Ответы",
    "Response body": "Тело ответа",
    "Response headers": "Заголовки ответа",
    "Server response": "Ответ сервера",
    "Request body": "Тело запроса",
    "Parameters": "Параметры",
    "No parameters": "Параметры отсутствуют",
    "Schemas": "Схемы",
    "Example Value": "Пример значения",
    "Model": "Модель",
    "Description": "Описание",
    "Code": "Код",
    "Details": "Детали",
    "Name": "Имя",
    "Type": "Тип",
    "Value": "Значение",
    "Default value": "Значение по умолчанию",
    "Required": "Обязательно",
    "Optional": "Необязательно",
    "Download": "Скачать",
    "Clear": "Очистить",
    "close": "закрыть",
    "Copied": "Скопировано",
    "Untitled": "Без названия"
  };

  const placeholderMap = {
    "Filter by tag": "Фильтр по тегу"
  };

  function translateTextNodes() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const updates = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.nodeValue;
      if (!text) {
        continue;
      }
      const trimmed = text.trim();
      if (!trimmed) {
        continue;
      }
      const translated = textMap[trimmed];
      if (!translated) {
        continue;
      }
      updates.push([node, text.replace(trimmed, translated)]);
    }
    for (const [node, value] of updates) {
      node.nodeValue = value;
    }
  }

  function translateAttributes() {
    document.querySelectorAll("[placeholder]").forEach((el) => {
      const value = el.getAttribute("placeholder");
      if (!value) {
        return;
      }
      const translated = placeholderMap[value.trim()];
      if (translated) {
        el.setAttribute("placeholder", translated);
      }
    });
  }

  function applyTranslation() {
    translateTextNodes();
    translateAttributes();
  }

  window.addEventListener("load", applyTranslation);
  new MutationObserver(applyTranslation).observe(document.body, {
    childList: true,
    subtree: true
  });
})();
</script>
"""
    localized_content = content.replace("</body>", f"{localization_script}</body>")
    return HTMLResponse(content=localized_content, status_code=base_response.status_code)


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_docs_oauth2_redirect() -> HTMLResponse:
    """Serve Swagger OAuth2 redirect page."""
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def landing_page() -> HTMLResponse:
    """Root page with quick navigation links."""
    return HTMLResponse(content=_landing_page_html())


@app.get("/portal", include_in_schema=False)
async def portal_page() -> FileResponse:
    """Serve frontend MVP page."""
    return FileResponse(_FRONTEND_DIR / "index.html")






@app.get("/portal/login", include_in_schema=False)
async def portal_login_page() -> RedirectResponse:
    """Redirect to portal with login auth mode."""
    return RedirectResponse(url="/portal?auth=login", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/portal/register", include_in_schema=False)
async def portal_register_page() -> RedirectResponse:
    """Redirect to portal with register auth mode."""
    return RedirectResponse(url="/portal?auth=register", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@app.get("/home", include_in_schema=False)
async def public_home_page() -> FileResponse:
    """Serve public website homepage."""
    return FileResponse(_PUBLIC_HOME_PAGE)

@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}


async def _is_database_ready() -> bool:
    """Return True if DB accepts basic queries."""
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database readiness check failed")
        return False


@app.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe endpoint with DB dependency check."""
    if not await _is_database_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not ready",
        )
    return {
        "status": "ready",
        "database": "ok",
        "timestamp": utc_now().isoformat(),
    }


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint(_: Request) -> Response:
    """Prometheus metrics endpoint."""
    return build_metrics_response()
