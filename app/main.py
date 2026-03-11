"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
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
