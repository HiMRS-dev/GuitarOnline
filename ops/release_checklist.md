# GuitarOnline Release Checklist

Use this checklist before promoting a build to a target environment.

## 1) Pre-Deploy

- Confirm target commit/tag and change log.
- Confirm environment variables are prepared (`.env`, secrets, proxy port override if used).
- If real on-call channels are required, render on-call Alertmanager config from env secrets:
  - `powershell -ExecutionPolicy Bypass -File scripts/render_alertmanager_oncall_config.ps1`
- Validate ops configuration:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_ops_configs.ps1`
- Optional image warmup (unstable network):
  - `powershell -ExecutionPolicy Bypass -File scripts/docker_warmup.ps1`
- Confirm backup plan and write access to backup location.

## 2) Backup

- Create fresh DB backup:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_backup.ps1`
- Verify backup file exists and is readable.

## 3) Deploy

- Standard production stack:
  - `docker compose -f docker-compose.prod.yml up --build -d`
- Single-site proxy profile:
  - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml up --build -d`
- On-call routing profile:
  - `docker compose -f docker-compose.prod.yml -f docker-compose.alerting.yml up --build -d`
- Single-site + on-call routing profile:
  - `docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml -f docker-compose.alerting.yml up --build -d`

## 4) Migrate

- Apply DB migrations:
  - `docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head`
- Confirm migration status:
  - `docker compose -f docker-compose.prod.yml exec -T app alembic current`

## 5) Smoke Tests

- API health:
  - `GET /health` returns `200`.
- API readiness:
  - `GET /ready` returns `200`.
- API docs:
  - `GET /docs` returns `200`.
- API metrics:
  - `GET /metrics` returns Prometheus payload.
- Portal:
  - `GET /portal` returns `200`.
  - `GET /portal/static/app.js` returns `200`.
  - `GET /portal/static/styles.css` returns `200`.
- Auth and portal basic flow:
  - register -> login -> profile (`/api/v1/identity/users/me`) succeeds.
- Alert routing synthetic test:
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_synthetic.ps1`
  - verify delivery in at least one real channel (Slack/PagerDuty/Email).
- Background worker:
  - `docker compose -f docker-compose.prod.yml logs --tail=100 outbox-worker` has no crash loop.

## 6) Post-Deploy Monitoring

- Confirm app container health in compose output.
- Confirm Prometheus target for `app` is UP.
- Confirm Grafana dashboard loads and reflects request traffic.
- Confirm Alertmanager config is loaded and no route errors are present.
- Confirm Alertmanager notifications for synthetic alerts are successful (no repeated notify failures in logs).

## 7) Rollback Procedure

- If release fails smoke checks:
  - `docker compose -f docker-compose.prod.yml down`
  - redeploy previous known-good image/commit.
- If migration rollback is required:
  - restore DB from backup:
    - `powershell -ExecutionPolicy Bypass -File scripts/db_restore.ps1 -InputFile <backup.sql>`
  - redeploy previous known-good app build.
- Re-run smoke checks on rolled-back version.

## 8) Sign-Off

- Record deployed commit/tag, timestamp, and operator.
- Record smoke-test results and any follow-up actions.
- Update checkpoint/report status in project docs.
