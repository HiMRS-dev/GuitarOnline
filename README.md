# GuitarOnline Backend

Production-ready modular monolith backend for an online guitar school.

## Quick start

1. Copy env file:
   - `cp .env.example .env`
2. Run containers:
   - `docker compose up --build`
3. Open docs:
   - `http://localhost:8000/docs`

## Migrations

- Create revision:
  - `poetry run alembic revision --autogenerate -m "init"`
- Apply migrations:
  - `poetry run alembic upgrade head`

## Workers

- Run notifications outbox worker once:
  - `poetry run python -m app.workers.outbox_notifications_worker`
- Run in polling mode:
  - `OUTBOX_WORKER_MODE=loop poetry run python -m app.workers.outbox_notifications_worker`

## Delivery Observability

- Admin API endpoint for delivery metrics:
  - `GET /api/v1/notifications/delivery/metrics?max_retries=5`
- Metrics include notification status totals and outbox queue/dead-letter counts.
