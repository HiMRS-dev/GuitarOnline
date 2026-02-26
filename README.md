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
  - `outbox-worker` (notifications outbox consumer loop),
  - `prometheus` (metrics scraping backend, port `9090`),
  - `alertmanager` (alert routing backend, port `9093`),
  - `grafana` (dashboards UI, port `3000`).
- Apply migrations after deploy:
  - `docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head`

### One-Click Deploy Pipeline

- GitHub Actions workflow:
  - `.github/workflows/deploy.yml`
- Trigger:
  - `workflow_dispatch` with required confirmation input `DEPLOY`.
- Required GitHub repository secrets:
  - `DEPLOY_HOST`
  - `DEPLOY_PORT` (optional, defaults to `22`)
  - `DEPLOY_USER`
  - `DEPLOY_PATH` (absolute target path, e.g. `/opt/guitaronline`)
  - `DEPLOY_SSH_PRIVATE_KEY`
  - `DEPLOY_KNOWN_HOSTS` (optional; when empty workflow runs `ssh-keyscan`)
  - `PROD_ENV_FILE_B64` (base64-encoded production `.env`)
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

## Demo Data Bootstrap (Non-Production)

- Seed script:
  - `py -m poetry run python scripts/seed_demo_data.py`
- Dockerized run (app container):
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/seed_demo_data.py`
- Script behavior:
  - idempotent and safe for repeated runs,
  - creates/updates demo users and teacher profile,
  - creates missing future teacher slots,
  - ensures at least one active student package.
- Safety:
  - by default script refuses to run when `APP_ENV` is `production`/`prod`,
  - override is possible only with explicit `--allow-production`.
- Demo credentials (for local/demo environments only):
  - `demo-admin@guitaronline.dev / DemoPass123!`
  - `demo-teacher@guitaronline.dev / DemoPass123!`
  - `demo-student@guitaronline.dev / DemoPass123!`

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
