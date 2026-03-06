# GuitarOnline Production Hardening Checklist

Use this checklist to move from "working deploy" to repeatable reliability.

## 1) Healthcheck Endpoint Verification

- Confirm liveness endpoint returns `200`:
  - `curl -fsS http://127.0.0.1:8000/health`
- Confirm readiness endpoint returns `200`:
  - `curl -fsS http://127.0.0.1:8000/ready`
- Confirm metrics endpoint is reachable:
  - `curl -fsS http://127.0.0.1:8000/metrics | head`
- Confirm portal assets are served:
  - `curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/portal`
  - `curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/portal/static/app.js`
- Keep `run_smoke=true` in deploy workflow for production releases.
- Confirm deploy smoke logs include role gate marker:
  - `Role-based release gate passed.`

## 2) Log Rotation Baseline

- Enable host-level log rotation for Docker container logs (`/var/lib/docker/containers/*/*.log`) or configure daemon-level JSON log limits:
  - `max-size` (example: `10m`)
  - `max-file` (example: `5`)
- Ensure `journalctl --disk-usage` stays within acceptable limits.
- Confirm rotation policy is active after daemon restart:
  - `docker info | grep -i "Logging Driver"`
- Verify no container is producing unbounded logs during normal load.

## 3) Monitoring Hooks and Alert Routing

- Confirm Prometheus target for `app` is `UP` in UI (`:9090`).
- Confirm Alertmanager route tree is loaded and has no config errors (`:9093`).
- Confirm Grafana dashboard loads and tracks request/error/latency panels (`:3000`).
- Fire synthetic alert and confirm delivery in at least one real channel:
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_and_verify.ps1`
  - strict routing verification:
    - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_and_verify.ps1 -RequireAllIntegrations`
  - fallback submit-only helper:
    - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_synthetic.ps1`
- Run synthetic operational critical-path probe:
  - `docker compose -f docker-compose.prod.yml exec -T app python scripts/synthetic_ops_check.py`
  - confirm output includes `Synthetic ops check passed.`
- Keep scheduled remote probe enabled:
  - `.github/workflows/synthetic-ops-check.yml` (hourly cron + manual dispatch).
- Use maintenance silences during planned releases and expire after rollout:
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_create_silence.ps1 -DurationMinutes 90 -Comment "planned release"`
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_expire_silence.ps1 -SilenceId <id>`

## 4) Rollback Verification Safety

- Keep `run_backup=true` on production deploys.
- Keep scheduled backup retention workflow enabled:
  - `.github/workflows/backup-schedule-retention.yml` (daily at `02:30 UTC`).
- Keep restore rehearsal workflow enabled and review latest RPO/RTO artifact:
  - `.github/workflows/restore-rehearsal.yml` (weekly at `03:20 UTC`).
- Keep monthly rollback drill workflow enabled and review latest report artifact:
  - `.github/workflows/rollback-drill.yml` (first Monday at `04:10 UTC`).
  - keep default guard (`allow_production=false`) and run on non-production target.
- Ensure each release has a known previous-good ref (branch/tag/SHA).
- Verify deploy rollback trap can return to previous SHA on failure (`scripts/deploy_remote.sh`).
- Rehearse restore procedure on a non-production host:
  - `bash scripts/verify_backup_restore.sh`
- Document a rollback drill result:
  - release ref under test,
  - rollback trigger used (failed smoke/migration),
  - restore result and timestamps,
  - operator and follow-up actions.

## 5) Cadence

- Per deploy: sections 1 and 4.
- Weekly: sections 2 and 3.
- Monthly: full checklist + one rollback drill simulation.
  - preferred path: run/review `.github/workflows/rollback-drill.yml`.
- Monthly: rerun `python scripts/admin_perf_baseline.py` and compare p95 values with:
  - `docs/perf/admin_perf_baseline_2026-03-06.md`,
  - `docs/perf/admin_perf_optimization_2026-03-06.md`,
  - latest comparison report (example): `docs/perf/admin_perf_baseline_compare_2026-03-06_r2.md`.
- Monthly: review latest `supply-chain-security-artifacts` from CI (`pip_audit.json`, `npm_audit.json`, `backend_sbom_cyclonedx.json`) and keep `ops/security/pip_audit_ignore.txt` empty unless a short-lived, reviewed exception is strictly required.
- Monthly: run secret-rotation dry-run and archive report:
  - `py -m poetry run python scripts/secret_rotation_dry_run.py --env-file .env --rotation-target auto`
  - runbook: `ops/secret_rotation_playbook.md`.
