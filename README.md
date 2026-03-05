# GuitarOnline Backend

Production-ready modular monolith backend for an online guitar school.

## Quick start

1. Copy env file:
   - `cp .env.example .env`
   - in production, set a non-placeholder `SECRET_KEY` (startup rejects `change-me*`)
   - optional alias: `JWT_SECRET` (if set, it overrides `SECRET_KEY`)
   - set admin frontend CORS origin in `FRONTEND_ADMIN_ORIGIN` (default `http://localhost:5173`)
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

## Development Runbook

- Backend local setup:
  - `py -m poetry install`
  - `cp .env.example .env`
  - `docker compose up -d db redis`
  - `py -m poetry run alembic upgrade head`
  - `py -m poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Migrations:
  - create revision: `py -m poetry run alembic revision --autogenerate -m "change_name"`
  - apply migrations: `py -m poetry run alembic upgrade head`
- Demo seed data:
  - local run: `py -m poetry run python scripts/seed_demo_data.py`
  - docker run: `docker compose -f docker-compose.prod.yml exec -T app python scripts/seed_demo_data.py`
- Workers local run:
  - notifications outbox worker once:
    - `py -m poetry run python -m app.workers.outbox_notifications_worker`
  - notifications outbox worker loop:
    - `NOTIFICATIONS_OUTBOX_WORKER_MODE=loop py -m poetry run python -m app.workers.outbox_notifications_worker`
  - booking HOLD expirer worker loop:
    - `BOOKING_HOLDS_EXPIRER_MODE=loop py -m poetry run python -m app.workers.booking_holds_expirer`
  - packages expirer worker loop:
    - `PACKAGES_EXPIRER_MODE=loop py -m poetry run python -m app.workers.packages_expirer`
  - 24h lesson reminder worker loop:
    - `LESSON_REMINDER_24H_WORKER_MODE=loop py -m poetry run python -m app.workers.lesson_reminder_24h_worker`
- `web-admin` local run:
  - `cd web-admin`
  - `cp .env.example .env`
  - `npm install`
  - `npm run dev`
  - open `http://localhost:5173` and ensure `VITE_API_BASE_URL` points to backend API.

## Deployment Baseline

- Start production-oriented compose stack:
  - `docker compose -f docker-compose.prod.yml up --build -d`
- Optional single-site reverse-proxy profile (one public entrypoint):
  - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml up --build -d`
- Optional admin UI profile (`web-admin` static build):
  - `docker compose -f docker-compose.prod.yml --profile admin-ui up --build -d`
- Optional single-site + admin UI profile:
  - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml --profile admin-ui up --build -d`
- Optional real on-call routing profile (requires rendered on-call Alertmanager config):
  - `powershell -ExecutionPolicy Bypass -File scripts/render_alertmanager_oncall_config.ps1`
  - `docker compose -f docker-compose.prod.yml -f docker-compose.alerting.yml up --build -d`
- Optional single-site + on-call profile:
  - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml -f docker-compose.alerting.yml up --build -d`
- Optional warmup for flaky networks (pull images with retries before deploy):
  - `powershell -ExecutionPolicy Bypass -File scripts/docker_warmup.ps1`
- Included services:
  - `db` (PostgreSQL),
  - `redis` (shared auth rate-limiter state),
  - `app` (FastAPI API),
  - `admin-ui` (optional `web-admin` static UI, enabled by `--profile admin-ui`),
  - `outbox-worker` (notifications outbox consumer loop),
  - `booking-holds-expirer` (periodic HOLD expiration worker),
  - `packages-expirer` (periodic package expiration worker),
  - `prometheus` (metrics scraping backend, port `9090`),
  - `alertmanager` (alert routing backend, port `9093`),
  - `grafana` (dashboards UI, port `3000`).
- Apply migrations after deploy:
  - `docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head`
- Run post-deploy smoke script:
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/deploy_smoke_check.py`
- Run load sanity scenario (~1000 weekly slots + admin list envelope checks):
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/load_sanity.py`
  - optional custom target (must stay within bulk-create cap):
    - `docker compose -f docker-compose.prod.yml exec -T -e LOAD_SANITY_TARGET_SLOTS=900 app python scripts/load_sanity.py`
- Explicit ops probe verification after smoke:
  - `curl -fsS http://localhost:8000/health`
  - `curl -fsS http://localhost:8000/ready`
  - `curl -fsS http://localhost:8000/metrics | grep -E "^(http_requests_total|http_request_duration_seconds)"`

## Production Config Matrix

### Runtime `.env` keys

| Key | Required | Scope | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | Yes | app/workers | Use `production` for prod controls. |
| `SECRET_KEY` | Yes | app/workers | Canonical JWT signing secret unless `JWT_SECRET` is set. |
| `JWT_SECRET` | No | app/workers | Backward-compatible alias; when set, overrides `SECRET_KEY`. |
| `DATABASE_URL` | Yes | app/workers | Async SQLAlchemy DSN for API and workers. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Yes | compose `db` | Required by PostgreSQL container in production compose. |
| `AUTH_RATE_LIMIT_BACKEND` | Yes | app/workers | `redis` recommended for production (`memory` only with explicit ack). |
| `REDIS_URL` | Conditionally yes | app/workers | Mandatory when `AUTH_RATE_LIMIT_BACKEND=redis`. |
| `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION` | Conditionally yes | app/workers | Must be `true` only for `memory` backend in production. |
| `FRONTEND_ADMIN_ORIGIN` | Yes | app CORS | Allowed origins for admin frontend CORS policy. |
| `ADMIN_UI_API_BASE_URL` | No | admin-ui profile | Build-time API base for `web-admin` Docker profile. |
| `ADMIN_UI_BASE_PATH` | No | admin-ui profile | Build-time base path for `web-admin` (`/admin/` by default). |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | No | monitoring | Defaults exist, but set explicit secure values in production. |

### CI/CD secrets

| Secret | Required | Workflow | Notes |
| --- | --- | --- | --- |
| `DEPLOY_HOST` | Yes | deploy, backup-restore-verify | Target server host/IP. |
| `DEPLOY_USER` | Yes | deploy, backup-restore-verify | SSH user. |
| `DEPLOY_PATH` | Yes | deploy, backup-restore-verify | Absolute path on target host. |
| `DEPLOY_SSH_PRIVATE_KEY` | Yes | deploy, backup-restore-verify | SSH authentication key. |
| `PROD_ENV_FILE_B64` | Yes | deploy | Base64 payload used to write `${DEPLOY_PATH}/.env`. |
| `DEPLOY_PORT` | No | deploy, backup-restore-verify | Defaults to `22`. |
| `DEPLOY_KNOWN_HOSTS` | No | deploy, backup-restore-verify | Optional host-key pinning override. |
| `AUTO_DEPLOY_ENABLED` | No | deploy | `true` enables push-triggered deploy on `main`. |

### Precedence Rules

1. JWT secret precedence: `JWT_SECRET` overrides `SECRET_KEY` when both are set.
2. Rate limiter backend:
   - `AUTH_RATE_LIMIT_BACKEND=redis` requires `REDIS_URL`;
   - `AUTH_RATE_LIMIT_BACKEND=memory` in production requires
     `AUTH_RATE_LIMIT_ALLOW_IN_MEMORY_IN_PRODUCTION=true`.
3. Deploy source of truth: `PROD_ENV_FILE_B64` is decoded by deploy workflow and overwrites
   `${DEPLOY_PATH}/.env` on target host.
4. Admin UI profile wiring:
   - `ADMIN_UI_API_BASE_URL` and `ADMIN_UI_BASE_PATH` apply only when `--profile admin-ui` is enabled.

### One-Click Deploy Pipeline

- GitHub Actions workflow:
  - `.github/workflows/deploy.yml`
- Trigger:
  - `workflow_dispatch` with required confirmation input `DEPLOY`.
  - `push` to `main` when repository secret `AUTO_DEPLOY_ENABLED=true`.
- Required GitHub repository secrets:
  - `DEPLOY_HOST`
  - `DEPLOY_PORT` (optional, defaults to `22`)
  - `DEPLOY_USER`
  - `DEPLOY_PATH` (absolute target path, e.g. `/opt/guitaronline`)
  - `DEPLOY_SSH_PRIVATE_KEY`
  - `DEPLOY_KNOWN_HOSTS` (optional; when empty workflow runs `ssh-keyscan`)
  - `PROD_ENV_FILE_B64` (base64-encoded production `.env`)
- Optional GitHub repository secrets:
  - `AUTO_DEPLOY_ENABLED`:
    - set to `true` to enable automatic deploy on every push to `main`,
    - keep unset or non-`true` to keep deploy in manual-only mode.
- Build `PROD_ENV_FILE_B64` value from local `.env`:
  - `powershell -ExecutionPolicy Bypass -File scripts/encode_env_base64.ps1`
  - copy output and set it as repository secret `PROD_ENV_FILE_B64`.
- Recommended one-command secret sync helper:
  - local env file -> GitHub secret:
    - `powershell -ExecutionPolicy Bypass -File scripts/update_github_secret_prod_env.ps1`
  - remote server env -> GitHub secret:
    - `powershell -ExecutionPolicy Bypass -File scripts/update_github_secret_prod_env.ps1 -RemoteHost 144.31.77.239 -RemoteUser deploy -RemoteEnvPath /opt/guitaronline/.env`
  - auth requirements:
    - either run `gh auth login` once, or set `GH_TOKEN`/`GITHUB_TOKEN` for current shell.
- Runtime options:
  - `ref` (branch/tag/SHA),
  - `profile` (`standard` or `proxy`),
  - `run_backup` (`true/false`),
  - `run_smoke` (`true/false`).
- Push-mode defaults (when triggered by `push`):
  - `ref=${GITHUB_SHA}`,
  - `profile=standard`,
  - `run_backup=true`,
  - `run_smoke=true`.
- Workflow behavior:
  - bootstraps repository metadata on target host when `${DEPLOY_PATH}` has no `.git` (no manual pre-clone required),
  - uploads `.env` from `PROD_ENV_FILE_B64` to `${DEPLOY_PATH}/.env`,
  - performs compose deploy and DB migrations,
  - runs post-deploy smoke checks (`/health`, `/ready`, `/docs`, `/metrics`, `/portal`, static assets, auth flow),
  - performs automatic rollback to previous git SHA when deploy/migrate/smoke fails.
- Secret safety controls:
  - `.env` is ignored by git (`.gitignore`),
  - CI hard-fails if `.env` appears in tracked files,
  - production `.env` is delivered from GitHub Secrets during deploy and is not stored in repository history.

### Single-Site Runtime Profile (Reverse Proxy)

- Compose bundle:
  - `docker-compose.prod.yml` + `docker-compose.proxy.yml`
- Public entrypoint:
  - `http://localhost:${PROXY_PUBLIC_PORT:-8080}`
- Canonical URLs behind proxy:
  - root: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/`
  - portal: `http://localhost:${PROXY_PUBLIC_PORT:-8080}/portal`
  - admin UI (when `--profile admin-ui` is enabled): `http://localhost:${PROXY_PUBLIC_PORT:-8080}/admin/`
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
  - for admin UI deployment, set:
    - `ADMIN_UI_API_BASE_URL` (default `/api/v1`),
    - `ADMIN_UI_BASE_PATH` (default `/admin/`).

## Migrations

- Create revision:
  - `poetry run alembic revision --autogenerate -m "init"`
- Apply migrations:
  - `poetry run alembic upgrade head`

## Secret Leak Prevention

- CI guardrails:
  - `.github/workflows/ci.yml` runs `python scripts/secret_guard.py --mode repo`,
  - CI fails if `.env` is ever tracked in git.
- Local pre-commit guardrails:
  - install hooks once:
    - `powershell -ExecutionPolicy Bypass -File scripts/install_git_hooks.ps1`
  - hook path:
    - `.githooks/pre-commit` (runs `scripts/secret_guard.py --mode staged`).
- False-positive override (explicit and reviewable):
  - add inline marker in the line: `secret-scan: allow`.

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
- CORS env:
  - `FRONTEND_ADMIN_ORIGIN` (comma-separated allowed origins for admin frontend)
- Security gate regression checks:
  - `py -m poetry run pytest -q tests/test_config_security.py tests/test_identity_rate_limit.py tests/test_security_surface.py tests/test_pii_field_visibility.py`
  - scope covered by this gate:
    - CORS policy wiring,
    - auth rate-limit dependencies,
    - response-model minimization for identity endpoints (no password hash/internal secret fields),
    - role-based PII field visibility (email fields exposed only on identity/admin contracts).

## Workers

- Run notifications outbox worker once:
  - `poetry run python -m app.workers.outbox_notifications_worker`
- Run in polling mode:
  - `NOTIFICATIONS_OUTBOX_WORKER_MODE=loop poetry run python -m app.workers.outbox_notifications_worker`
  - legacy env alias is still accepted: `OUTBOX_WORKER_MODE=loop`.
- Run booking HOLD expiration worker once:
  - `poetry run python -m app.workers.booking_holds_expirer`
- Run booking HOLD expiration worker in polling mode:
  - `BOOKING_HOLDS_EXPIRER_MODE=loop poetry run python -m app.workers.booking_holds_expirer`
- Run package expiration worker once:
  - `poetry run python -m app.workers.packages_expirer`
- Run package expiration worker in polling mode:
  - `PACKAGES_EXPIRER_MODE=loop poetry run python -m app.workers.packages_expirer`
- Run 24h lesson reminder worker once:
  - `poetry run python -m app.workers.lesson_reminder_24h_worker`
- Run 24h lesson reminder worker in polling mode:
  - `LESSON_REMINDER_24H_WORKER_MODE=loop poetry run python -m app.workers.lesson_reminder_24h_worker`

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

## Demo Data Bootstrap (Non-Production)

- Seed script:
  - `py -m poetry run python scripts/seed_demo_data.py`
- Dockerized run (app container):
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/seed_demo_data.py`
- Script behavior:
  - idempotent and safe for repeated runs,
  - creates/updates baseline users:
    - 1 admin,
    - 3 teachers,
    - 5 students,
  - creates/updates verified teacher profiles for all demo teachers,
  - creates 10 future slots distributed across demo teachers,
  - ensures 2 active student packages.
- Safety:
  - by default script refuses to run when `APP_ENV` is `production`/`prod`,
  - override is possible only with explicit `--allow-production`.
- Demo credentials (for local/demo environments only):
  - `demo-admin@guitaronline.dev / DemoPass123!`
  - `demo-teacher-1@guitaronline.dev / DemoPass123!`
  - `demo-teacher-2@guitaronline.dev / DemoPass123!`
  - `demo-teacher-3@guitaronline.dev / DemoPass123!`
  - `demo-student-1@guitaronline.dev / DemoPass123!`
  - `demo-student-2@guitaronline.dev / DemoPass123!`
  - `demo-student-3@guitaronline.dev / DemoPass123!`
  - `demo-student-4@guitaronline.dev / DemoPass123!`
  - `demo-student-5@guitaronline.dev / DemoPass123!`

## Admin Contract Docs

- Admin API contracts and DTO examples:
  - `docs/ADMIN_API.md`
- Domain source-of-truth rules for Slot/Booking/Lesson:
  - `docs/DOMAIN_RULES.md`

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
- Real on-call config is generated from environment secrets:
  - `powershell -ExecutionPolicy Bypass -File scripts/render_alertmanager_oncall_config.ps1`
- Generated file (ignored by git):
  - `ops/alertmanager/alertmanager.oncall.generated.yml`
- Compose override for generated config:
  - `docker-compose.alerting.yml`
- Required env secrets:
  - `ALERTMANAGER_SLACK_WEBHOOK_URL`
  - `ALERTMANAGER_SLACK_CHANNEL`
  - `ALERTMANAGER_PAGERDUTY_ROUTING_KEY`
  - `ALERTMANAGER_SMTP_SMARTHOST`
  - `ALERTMANAGER_SMTP_FROM`
  - `ALERTMANAGER_SMTP_TO`
  - `ALERTMANAGER_SMTP_AUTH_USERNAME`
  - `ALERTMANAGER_SMTP_AUTH_PASSWORD`
  - `ALERTMANAGER_SMTP_REQUIRE_TLS`
- Severity routing in generated config:
  - when SMTP email is configured: `warning` -> `email-warning`
  - when SMTP email is absent but Slack is configured: `warning` -> `slack-warning`
  - `critical` -> `slack-critical` (+ `pagerduty-critical` when PagerDuty key is configured)
- Anti-noise controls:
  - warning routes use slower repeat interval (`6h`),
  - critical routes use faster repeat interval (`1h`),
  - inhibition suppresses warning alerts when matching critical is active (`alertname + service`),
  - `GuitarOnlineApiDown` inhibits `GuitarOnlineApiHigh5xxRate` / `GuitarOnlineApiHighP95Latency` for the same service.
- Fire synthetic alerts for routing validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_synthetic.ps1`
  - confirm delivery in at least one real target channel (Slack/PagerDuty/Email).
- Maintenance silence baseline:
  - create temporary silence (warning by default):
    - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_create_silence.ps1 -DurationMinutes 90 -Comment "planned release window"`
  - include critical alerts in silence (optional):
    - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_create_silence.ps1 -DurationMinutes 30 -IncludeCritical -Comment "planned maintenance"`
  - expire silence by ID:
    - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_expire_silence.ps1 -SilenceId <id>`

## Admin Operations

- Admin KPI overview endpoint:
  - `GET /api/v1/admin/kpi/overview`
- Admin sales KPI endpoint (UTC range):
  - `GET /api/v1/admin/kpi/sales?from_utc=<iso>&to_utc=<iso>`
- Response provides aggregated KPIs for users, bookings, lessons, payments, and packages.
- Sales KPI includes succeeded/refunded/net payment metrics and package paid-conversion counters for range.
- Admin operational overview endpoint:
  - `GET /api/v1/admin/ops/overview?max_retries=5`
- Response provides queue and consistency signals (outbox retries/dead-letter, stale holds, overdue packages).

## Operational Runbook

1. Check platform snapshot:
   - `GET /api/v1/admin/kpi/overview`
2. Check queue and consistency health:
   - `GET /api/v1/admin/ops/overview?max_retries=5`
3. If `stale_booking_holds > 0`:
   - worker `booking-holds-expirer` should clear them automatically,
   - if worker is disabled, run `POST /api/v1/booking/holds/expire` manually.
4. If `overdue_active_packages > 0`:
   - worker `packages-expirer` should clear them automatically,
   - if worker is disabled, run `POST /api/v1/billing/packages/expire` manually.
5. If `outbox_failed_dead_letter > 0`:
   - inspect `/api/v1/audit/outbox/pending` and `notifications` records,
   - reprocess only after root-cause fix.

## Backup and Restore

- Canonical minimum backup strategy for release operations:
  - backup script: `scripts/db_backup.ps1`,
  - restore script: `scripts/db_restore.ps1`,
  - release execution checklist: `ops/release_checklist.md` (section `2) Backup`).
- Create DB backup from dockerized PostgreSQL:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_backup.ps1`
- Create DB backup to a custom path:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_backup.ps1 -OutputFile backups/manual.sql`
- Restore DB from backup file:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_restore.ps1 -InputFile backups/manual.sql`
- Verify backup restore reproducibly against a temporary DB:
  - `bash scripts/verify_backup_restore.sh`
- Verify restore against a specific backup artifact:
  - `bash scripts/verify_backup_restore.sh backups/manual.sql`
- Recurring remote verification workflow:
  - `.github/workflows/backup-restore-verify.yml`
  - schedule: every Monday at `03:00 UTC`,
  - can also run manually via `workflow_dispatch` (`confirm=VERIFY`),
  - includes the same repository bootstrap logic for empty `${DEPLOY_PATH}`.

## Release Checklist

- End-to-end release runbook (deploy, migrate, smoke tests, rollback):
  - `ops/release_checklist.md`
- Reliability hardening runbook (health checks, log retention, monitoring, rollback drills):
  - `ops/production_hardening_checklist.md`

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
  - `docker-compose.prod.yml + docker-compose.alerting.yml` merged syntax (when generated on-call config exists),
  - Prometheus config and alert rules (`promtool`),
  - baseline Alertmanager config (`amtool`),
  - on-call Alertmanager config (`amtool`, when generated on-call config exists).
