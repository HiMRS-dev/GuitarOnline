# GuitarOnline Backend

Production-ready modular monolith backend for an online guitar school.

## Quick start

1. Copy env file:
   - `cp .env.example .env`
   - in production, set a non-default `SECRET_KEY` (startup rejects `change-me`)
2. Run containers:
   - `docker compose up --build`
3. Open docs:
   - `http://localhost:8000/docs`

## Migrations

- Create revision:
  - `poetry run alembic revision --autogenerate -m "init"`
- Apply migrations:
  - `poetry run alembic upgrade head`

## Security Controls

- Identity endpoints are rate-limited per client IP:
  - `POST /api/v1/identity/auth/register`
  - `POST /api/v1/identity/auth/login`
  - `POST /api/v1/identity/auth/refresh`
- Configure limits with env vars:
  - `AUTH_RATE_LIMIT_WINDOW_SECONDS`
  - `AUTH_RATE_LIMIT_REGISTER_REQUESTS`
  - `AUTH_RATE_LIMIT_LOGIN_REQUESTS`
  - `AUTH_RATE_LIMIT_REFRESH_REQUESTS`

## Workers

- Run notifications outbox worker once:
  - `poetry run python -m app.workers.outbox_notifications_worker`
- Run in polling mode:
  - `OUTBOX_WORKER_MODE=loop poetry run python -m app.workers.outbox_notifications_worker`

## Delivery Observability

- Admin API endpoint for delivery metrics:
  - `GET /api/v1/notifications/delivery/metrics?max_retries=5`
- Metrics include notification status totals and outbox queue/dead-letter counts.

## Admin Operations

- Admin KPI overview endpoint:
  - `GET /api/v1/admin/kpi/overview`
- Response provides aggregated KPIs for users, bookings, lessons, payments, and packages.
- Admin operational overview endpoint:
  - `GET /api/v1/admin/ops/overview?max_retries=5`
- Response provides queue and consistency signals (outbox retries/dead-letter, stale holds, overdue packages).

## Operational Runbook

1. Check platform snapshot:
   - `GET /api/v1/admin/kpi/overview`
2. Check queue and consistency health:
   - `GET /api/v1/admin/ops/overview?max_retries=5`
3. If `stale_booking_holds > 0`:
   - run `POST /api/v1/booking/holds/expire`
4. If `overdue_active_packages > 0`:
   - run `POST /api/v1/billing/packages/expire`
5. If `outbox_failed_dead_letter > 0`:
   - inspect `/api/v1/audit/outbox/pending` and `notifications` records,
   - reprocess only after root-cause fix.
