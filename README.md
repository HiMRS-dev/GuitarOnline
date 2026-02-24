# GuitarOnline Backend

Production-ready modular monolith backend for an online guitar school.

## Quick start

1. Copy env file:
   - `cp .env.example .env`
   - in production, set a non-placeholder `SECRET_KEY` (startup rejects `change-me*`)
   - choose auth limiter backend:
     - recommended production mode: `AUTH_RATE_LIMIT_BACKEND=redis` with valid `REDIS_URL`
     - fallback mode: `AUTH_RATE_LIMIT_BACKEND=memory` + explicit
       `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION=true`
2. Run containers:
   - `docker compose up --build`
3. Open docs:
   - `http://localhost:8000/docs`
   - root landing page: `http://localhost:8000/`
   - frontend MVP portal: `http://localhost:8000/portal`
   - VS Code Live Server helper page: `http://127.0.0.1:5500/`
4. Probes:
   - liveness: `http://localhost:8000/health`
   - readiness (DB-aware): `http://localhost:8000/ready`
   - metrics (Prometheus format): `http://localhost:8000/metrics`

## Deployment Baseline

- Start production-oriented compose stack:
  - `docker compose -f docker-compose.prod.yml up --build -d`
- Optional single-site reverse-proxy profile (one public entrypoint):
  - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml up --build -d`
- Optional warmup for flaky networks (pull images with retries before deploy):
  - `powershell -ExecutionPolicy Bypass -File scripts/docker_warmup.ps1`
- Included services:
  - `db` (PostgreSQL),
  - `redis` (shared auth rate-limiter state),
  - `app` (FastAPI API),
  - `outbox-worker` (notifications outbox consumer loop),
  - `prometheus` (metrics scraping backend, port `9090`),
  - `alertmanager` (alert routing backend, port `9093`),
  - `grafana` (dashboards UI, port `3000`).
- Apply migrations after deploy:
  - `docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head`

### Single-Site Runtime Profile (Reverse Proxy)

- Compose bundle:
  - `docker-compose.prod.yml` + `docker-compose.proxy.yml`
- Public entrypoint:
  - `http://localhost:${PROXY_PUBLIC_PORT:-8080}`
- Canonical URLs behind proxy:
  - root: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/`
  - portal: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/portal`
  - API: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/api/v1`
  - docs: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/docs`
  - health: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/health`
  - readiness: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/ready`
  - metrics: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/metrics`
- Health checks:
  - proxy container probes `/health` through upstream app.
  - app service remains healthchecked on `http://localhost:8000/health` inside container.
- Note:
  - in proxy profile, host binding for `app:8000` is removed (`ports: []` override),
    so external traffic should use proxy URL only.

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
  - `AUTH_RATE_LIMIT_BACKEND` (`memory` or `redis`)
  - `AUTH_RATE_LIMIT_REDIS_NAMESPACE` (Redis key prefix for limiter buckets)
  - `REDIS_URL` (required when backend is `redis`)
  - `AUTH_RATE_LIMIT_WINDOW_SECONDS`
  - `AUTH_RATE_LIMIT_REGISTER_REQUESTS`
  - `AUTH_RATE_LIMIT_LOGIN_REQUESTS`
  - `AUTH_RATE_LIMIT_REFRESH_REQUESTS`
  - `AUTH_RATE_LIMIT_TRUSTED_PROXY_IPS` (comma-separated proxy IPs allowed to supply `X-Forwarded-For`)
  - `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION` (required only when `AUTH_RATE_LIMIT_BACKEND=memory` in production)

## Workers

- Run notifications outbox worker once:
  - `poetry run python -m app.workers.outbox_notifications_worker`
- Run in polling mode:
  - `OUTBOX_WORKER_MODE=loop poetry run python -m app.workers.outbox_notifications_worker`

## Frontend MVP Portal

- Portal URL:
  - `GET /portal`
- Built-in screens:
  - register/login,
  - current user profile,
  - open slots,
  - my bookings,
  - my lesson packages (student role).
- Static assets are served by FastAPI at:
  - `/portal/static/*`

## Delivery Observability

- Admin API endpoint for delivery metrics:
  - `GET /api/v1/notifications/delivery/metrics?max_retries=5`
- Metrics include notification status totals and outbox queue/dead-letter counts.

## Platform Monitoring

- API exposes Prometheus-compatible metrics endpoint:
  - `GET /metrics`
- Production compose includes:
  - Prometheus scraping `app:8000/metrics`,
  - Alertmanager for alert routing,
  - Grafana with pre-provisioned dashboard: `GuitarOnline API Overview`.
- Open UIs:
  - `http://localhost:9090`
  - `http://localhost:9093`
  - `http://localhost:3000` (default credentials from `.env`: `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`)
- Prometheus alert rules baseline:
  - API down for 2m,
  - 5xx ratio > 5% for 5m,
  - p95 latency > 1s for 10m.

## Alert Receiver Onboarding

- Current Alertmanager baseline receiver is local (`default-log`) and safe by default.
- For real on-call routing, use template:
  - `ops/alertmanager/alertmanager.receivers.example.yml`
- Add required receiver blocks to:
  - `ops/alertmanager/alertmanager.yml`
- Then update Alertmanager `route`/`routes` to map severities (`warning`/`critical`) to your real receivers.

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

## Backup and Restore

- Create DB backup from dockerized PostgreSQL:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_backup.ps1`
- Create DB backup to a custom path:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_backup.ps1 -OutputFile backups/manual.sql`
- Restore DB from backup file:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_restore.ps1 -InputFile backups/manual.sql`

## Docker Network Mitigation

- If Docker Hub pulls are unstable, pre-pull core runtime images with retries:
  - `powershell -ExecutionPolicy Bypass -File scripts/docker_warmup.ps1 -MaxRetries 6 -InitialDelaySeconds 3`
- Export local image cache (for offline reuse on this/another host):
  - `powershell -ExecutionPolicy Bypass -File scripts/docker_cache_export.ps1 -OutputFile backups/docker_images_cache.tar`
- Import image cache:
  - `powershell -ExecutionPolicy Bypass -File scripts/docker_cache_import.ps1 -InputFile backups/docker_images_cache.tar`
- Production compose uses `pull_policy: if_not_present` for external images to reduce unnecessary pull attempts.

## Ops Config Validation

- Validate production ops config bundle locally:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_ops_configs.ps1`
- Validation includes:
  - `docker-compose.prod.yml` syntax,
  - `docker-compose.prod.yml + docker-compose.proxy.yml` merged syntax,
  - Prometheus config and alert rules (`promtool`),
  - Alertmanager config (`amtool`).
