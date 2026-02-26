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
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_fire_synthetic.ps1`
- Use maintenance silences during planned releases and expire after rollout:
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_create_silence.ps1 -DurationMinutes 90 -Comment "planned release"`
  - `powershell -ExecutionPolicy Bypass -File scripts/alertmanager_expire_silence.ps1 -SilenceId <id>`

## 4) Rollback Verification Safety

- Keep `run_backup=true` on production deploys.
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
