# GuitarOnline Release Checklist

Use this checklist before promoting a build to a target environment.

## 1) Pre-Deploy

- Confirm target commit/tag and change log.
- Confirm environment variables are prepared (preferred: `PROD_ENV_FILE_B64` GitHub secret for deploy workflow; fallback: manual `.env`).
- Verify runtime env + CI/CD secrets against `README.md` section `Production Config Matrix`.
- If `.env` changed, refresh GitHub secret:
  - preferred one-command sync:
    - `powershell -ExecutionPolicy Bypass -File scripts/update_github_secret_prod_env.ps1`
  - if production env source of truth is on server:
    - `powershell -ExecutionPolicy Bypass -File scripts/update_github_secret_prod_env.ps1 -RemoteHost 144.31.77.239 -RemoteUser deploy -RemoteEnvPath /opt/guitaronline/.env`
  - fallback manual method:
    - `powershell -ExecutionPolicy Bypass -File scripts/encode_env_base64.ps1`
    - update repository secret `PROD_ENV_FILE_B64`.
- If real on-call channels are required, render on-call Alertmanager config from env secrets:
  - `powershell -ExecutionPolicy Bypass -File scripts/render_alertmanager_oncall_config.ps1`
- Validate ops configuration:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_ops_configs.ps1`
- Run security regression gate:
  - `py -m poetry run pytest -q tests/test_config_security.py tests/test_identity_rate_limit.py tests/test_security_surface.py tests/test_pii_field_visibility.py`
- Verify supply-chain security gate is green in CI (`supply-chain` job):
  - `.github/workflows/ci.yml`
  - expected artifact: `supply-chain-security-artifacts` (`pip_audit.json`, `npm_audit.json`, `backend_sbom_cyclonedx.json`, `summary.json`).
- Optional image warmup (unstable network):
  - `powershell -ExecutionPolicy Bypass -File scripts/docker_warmup.ps1`
- Optional maintenance silence before deploy (warning alerts by default):
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_create_silence.ps1 -DurationMinutes 90 -Comment "planned release window"`
- Confirm backup plan and write access to backup location.

## 2) Backup

- Canonical minimum scripts for this step:
  - backup: `scripts/db_backup.ps1`,
  - restore: `scripts/db_restore.ps1`.
- Create fresh DB backup:
  - `powershell -ExecutionPolicy Bypass -File scripts/db_backup.ps1`
- Verify backup file exists and is readable.
- Verify restore process against backup artifact:
  - `bash scripts/verify_backup_restore.sh <backup.sql>`
- Verify scheduled backup retention automation is healthy:
  - workflow `.github/workflows/backup-schedule-retention.yml` is enabled,
  - latest artifacts exist under `backups/scheduled/daily` (and `weekly` on weekly snapshot day).
- Verify restore rehearsal workflow produces RPO/RTO report artifact:
  - workflow `.github/workflows/restore-rehearsal.yml` is enabled,
  - latest run artifact includes `rpo_seconds` and `rto_seconds`.

## 3) Deploy

- Preferred one-click path (GitHub Actions):
  - run `.github/workflows/deploy.yml` (`workflow_dispatch`, confirm=`DEPLOY`).
  - choose runtime profile (`standard` or `proxy`) and optional backup/smoke toggles.
- Optional auto-deploy mode:
  - set repository secret `AUTO_DEPLOY_ENABLED=true` to deploy automatically on push to `main`.
  - for manual-only mode, remove this secret or set any value other than `true`.
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

- Required scripted smoke run:
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/deploy_smoke_check.py`
- Load sanity scenario (~1000 slots + admin slots envelope checks):
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/load_sanity.py`
  - expected output includes `Load sanity passed`.
  - script automatically falls back to legacy scheduling endpoints when admin slot endpoints are unavailable.
- Admin-heavy endpoint baseline snapshot:
  - `python scripts/admin_perf_baseline.py`
  - verify report is updated in `docs/perf/admin_perf_baseline_2026-03-06.md`.
  - compare against optimization report: `docs/perf/admin_perf_optimization_2026-03-06.md`.
- Explicit health/readiness/metrics verification (do not skip):
  - `curl -fsS http://localhost:8000/health`
  - `curl -fsS http://localhost:8000/ready`
  - `curl -fsS http://localhost:8000/metrics | grep -E "^(http_requests_total|http_request_duration_seconds)"`
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
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_and_verify.ps1`
  - strict mode for full integration matrix:
    - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_and_verify.ps1 -RequireAllIntegrations`
  - fallback submit-only helper:
    - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_synthetic.ps1`
- Synthetic critical-path ops probe:
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/synthetic_ops_check.py`
  - expected output includes `Synthetic ops check passed.`
- Background worker:
  - `docker compose -f docker-compose.prod.yml logs --tail=100 outbox-worker` has no crash loop.

## 6) Post-Deploy Monitoring

- Confirm app container health in compose output.
- Confirm Prometheus target for `app` is UP.
- Confirm Grafana dashboard loads and reflects request traffic.
- Confirm Alertmanager config is loaded and no route errors are present.
- Confirm Alertmanager notifications for synthetic alerts are successful (no repeated notify failures in logs).
- If maintenance silence was created, expire it after successful rollout:
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_expire_silence.ps1 -SilenceId <id>`

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
- For ongoing reliability controls, run:
  - `ops/production_hardening_checklist.md`
